"""Demo helpers: serve the specimen KYC documents so the UI can show the K01-K12 scenarios without
the presenter hunting for files. Read-only, restricted to the specimen set."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import DATA_DIR
from ..services.ocr import DOC_TYPES

router = APIRouter(prefix="/demo", tags=["demo"])

SAMPLES = [
    ("K02", "Clean set, photographed at an angle", "PASS"),
    ("K03", "Clean set", "PASS"),
    ("K04", "GST certificate photo is blurred", "NEEDS_FIX"),
    ("K05", "No Udyam certificate", "NEEDS_FIX"),
    ("K11", "Electricity bill is too old", "NEEDS_FIX"),
    ("K01", "GSTIN cancelled, Udyam number blank", "NEEDS_FIX"),
    ("K06", "GSTIN digit altered on certificate", "MANUAL_REVIEW"),
    ("K07", "Business name differs between documents", "MANUAL_REVIEW"),
]


@router.get("/kyc-samples")
def samples():
    return [dict(id=i, label=l, expected=e) for i, l, e in SAMPLES]


@router.get("/kyc-samples/{kid}/{doc_type}")
def sample_doc(kid: str, doc_type: str):
    if not re.fullmatch(r"K(0[1-9]|1[0-2])", kid) or doc_type not in DOC_TYPES:
        raise HTTPException(404, "no such sample")
    p = DATA_DIR / "kyc_documents" / f"{kid}_{doc_type}.png"
    if not p.exists():
        raise HTTPException(404, "that sample has no such document")
    return FileResponse(p, media_type="image/png")
