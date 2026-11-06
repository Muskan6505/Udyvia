"""Smart KYC API: consent -> upload (4 docs) -> validate -> decision. Withdraw deletes everything."""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..services.kyc_decision import run_kyc
from ..services.ocr import DOC_TYPES

router = APIRouter(prefix="/kyc", tags=["kyc"])

RETENTION_SECONDS = 24 * 3600          # uploads are deleted after 24h even if never withdrawn
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_TYPES = {"image/png": ".png", "image/jpeg": ".jpg"}
_ROOT = Path(tempfile.gettempdir()) / "udyam_kyc"
_SESSIONS: dict[str, dict] = {}

CONSENT_NOTICE = {
    "purpose": "Verify your business and the person signing for it so we can activate your Accel Business services.",
    "data_used": ["GST certificate", "Udyam certificate", "signatory ID", "address proof",
                  "details read from them (names, address, registration numbers)"],
    "retention": "Document images are deleted within 24 hours or as soon as you withdraw, whichever is first. "
                 "Identifiers are shown masked and never written to logs.",
    "withdraw": "You can withdraw consent at any time; this deletes your uploads and results.",
}


class ConsentIn(BaseModel):
    accepted: bool


class ValidateIn(BaseModel):
    declared_gstin: str | None = None
    udyam_waived: bool = False


def _purge(sid: str) -> None:
    s = _SESSIONS.pop(sid, None)
    if s:
        shutil.rmtree(s["dir"], ignore_errors=True)


def _purge_expired() -> None:
    now = time.time()
    for sid in [k for k, v in _SESSIONS.items() if v["expires"] < now]:
        _purge(sid)


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
    d.mkdir(parents=True, exist_ok=True)
    _SESSIONS[sid] = dict(dir=d, files={}, result=None, consented_at=time.time(), expires=time.time() + RETENTION_SECONDS)
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
    _purge(sid)
    return {"deleted": True}
