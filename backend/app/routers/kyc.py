"""Smart KYC API: consent -> upload (4 docs) -> validate -> decision. Withdraw deletes everything."""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..privacy import audit, policy
from ..services.kyc_decision import run_kyc
from ..services.ocr import DOC_TYPES

router = APIRouter(prefix="/kyc", tags=["kyc"])

RETENTION_SECONDS = policy.KYC_HOURS * 3600   # uploads are deleted after this even if never withdrawn (see privacy/retention.py)
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg"}
_ROOT = Path(tempfile.gettempdir()) / "udyam_kyc"
_SESSIONS: dict[str, dict] = {}

CONSENT_NOTICE = {
    "purpose": "Verify your business and the person signing for it so we can activate your Accel Business services.",
    "data_used": ["GST certificate", "Udyam certificate", "signatory ID", "address proof",
                  "details read from them (names, address, registration numbers)"],
    "retention": f"Document images and what we read from them are deleted within {policy.KYC_HOURS} hours, or as soon as "
                 "you withdraw, whichever is first. Documents are read on our own server and are never sent to an AI service. "
                 "Identifiers are shown masked and never written to logs.",
    "withdraw": "You can withdraw consent at any time; this deletes your uploads and results.",
}


class ConsentIn(BaseModel):
    accepted: bool


class ValidateIn(BaseModel):
    declared_gstin: str | None = None
    udyam_waived: bool = False


def _purge(sid: str, reason: str = "expired") -> None:
    s = _SESSIONS.pop(sid, None)
    if s:
        shutil.rmtree(s["dir"], ignore_errors=True)
        audit.log("kyc_data_deleted", sid, reason=reason, files=len(s["files"]))


def sweep_orphans(min_age_seconds: float = 60.0) -> int:
    """Deletes upload folders that no live session owns (for example after a server restart, when the in-memory
    session list is gone but the files are not). Without this, a restart would break the retention promise."""
    if not _ROOT.exists():
        return 0
    n = 0
    now = time.time()
    for d in _ROOT.iterdir():
        if d.name not in _SESSIONS and d.is_dir() and now - d.stat().st_mtime >= min_age_seconds:
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    if n:
        audit.log("kyc_data_deleted", None, reason="orphaned_after_restart", folders=n)
    return n


def _purge_expired() -> None:
    now = time.time()
    for sid in [k for k, v in _SESSIONS.items() if v["expires"] < now]:
        _purge(sid, "expired")


def get_session(sid: str) -> dict:
    _purge_expired()
    s = _SESSIONS.get(sid)
    if not s:
        raise HTTPException(404, "KYC session not found or expired")
    return s


@router.get("/consent")
def consent_notice():
    return CONSENT_NOTICE


@router.post("/consent")
def give_consent(body: ConsentIn):
    if not body.accepted:
        raise HTTPException(400, "Consent is required before uploading documents")
    _purge_expired()
    sid = uuid.uuid4().hex
    d = _ROOT / sid
    _ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    _SESSIONS[sid] = dict(dir=d, files={}, result=None, consented_at=time.time(), expires=time.time() + RETENTION_SECONDS)
    audit.log("consent_given", sid, purpose="kyc", retention_hours=policy.KYC_HOURS)
    return {"kyc_session_id": sid, "retention_hours": RETENTION_SECONDS // 3600}


@router.post("/{sid}/upload/{doc_type}")
async def upload(sid: str, doc_type: str, file: UploadFile = File(...)):
    s = get_session(sid)
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, f"doc_type must be one of {list(DOC_TYPES)}")
    ext = ALLOWED_TYPES.get(file.content_type or "")
    if not ext:
        raise HTTPException(415, "Please upload a PNG or JPEG image")
    blob = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(blob) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 8 MB")
    old = s["files"].get(doc_type)
    if old:
        Path(old).unlink(missing_ok=True)
    dest = s["dir"] / f"{doc_type}{ext}"      # server-chosen name: the client filename is never used
    dest.write_bytes(blob)
    dest.chmod(0o600)
    audit.log("document_uploaded", sid, doc_type=doc_type, bytes=len(blob))
    s["files"][doc_type] = str(dest)
    s["result"] = None                          # a new upload invalidates the previous decision
    return {"uploaded": sorted(s["files"]), "missing": [t for t in DOC_TYPES if t not in s["files"]]}


@router.post("/{sid}/validate")
def validate(sid: str, body: ValidateIn | None = None):
    s = get_session(sid)
    body = body or ValidateIn()
    res = run_kyc({t: s["files"].get(t) for t in DOC_TYPES}, declared_gstin=body.declared_gstin,
                  udyam_waived=body.udyam_waived)
    s["result"] = res
    audit.log("kyc_decided", sid, decision=res.decision, codes=sorted(res.codes()))
    return res.to_dict()


@router.get("/{sid}/result")
def result(sid: str):
    s = get_session(sid)
    if not s["result"]:
        raise HTTPException(409, "Not validated yet")
    return s["result"].to_dict()


@router.delete("/{sid}")
def withdraw(sid: str):
    get_session(sid)
    audit.log("consent_withdrawn", sid)
    _purge(sid, "withdrawn")
    return {"deleted": True}
