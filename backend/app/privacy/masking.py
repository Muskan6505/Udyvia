"""Masking and redaction of identifiers. Pure functions."""
from __future__ import annotations

import re

GSTIN = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b", re.I)
UDYAM = re.compile(r"\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b", re.I)
PHONE = re.compile(r"(?<![\dA-Za-z])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LONG_ID = re.compile(r"(?<!\d)\d{4}[\s-]?\d{4}[\s-]?\d{4}(?!\d)")        # 12-digit national-ID style numbers


def mask_gstin(g: str) -> str:
    return g[:2] + "•" * 9 + g[-4:]


def mask_udyam(u: str) -> str:
    return u[:8] + "•••" + u[-3:]


def mask_phone(p: str) -> str:
    d = re.sub(r"\D", "", p)
    return "•" * max(0, len(d) - 4) + d[-4:]


def scrub(text: str, mode: str = "mask") -> str:
    """mode='mask': keep a recognisable stub (for logs). mode='redact': placeholders only (for third parties)."""
    if not text:
        return text
    m = mode == "mask"
    text = GSTIN.sub(lambda x: mask_gstin(x.group(0).upper()) if m else "[GSTIN]", text)
    text = UDYAM.sub(lambda x: mask_udyam(x.group(0).upper()) if m else "[UDYAM]", text)
    text = EMAIL.sub("[email]", text)
    text = PHONE.sub(lambda x: mask_phone(x.group(0)) if m else "[phone]", text)
    text = LONG_ID.sub("[id]", text)
    return text


def contains_identifier(text: str) -> bool:
    return any(p.search(text or "") for p in (GSTIN, UDYAM, PHONE, EMAIL, LONG_ID))
