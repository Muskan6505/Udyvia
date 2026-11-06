"""Image quality gate + OCR + label-driven field extraction.

Engine is Tesseract (free, runs offline). `vision_fallback` is the hook where a free-tier vision LLM
(e.g. Gemini Flash) can be plugged in for photos that Tesseract cannot read; it is OFF by default so
the whole KYC path is deterministic and works with no API key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import pytesseract

from ..config import BLUR_MIN_LAPLACIAN_VAR, MIN_IMAGE_SIDE_PX

DOC_TYPES = ("gst_certificate", "udyam_certificate", "signatory_id", "address_proof")

# header keyword -> doc type, used to catch "uploaded the wrong document in this slot"
_HEADERS = {
    "gst_certificate": "gst registration",
    "udyam_certificate": "udyam registration",
    "signatory_id": "signatory id",
    "address_proof": "electricity bill|water bill|utility|bill",
}

# label (as printed) -> canonical field name
_LABELS = {
    "gst_certificate": {
        "gstin": "gstin", "legal name": "legal_name", "trade name": "trade_name", "constitution": "constitution",
        "address of principal": "address", "date of liability": "registration_date", "type of registration": "reg_type",
    },
    "udyam_certificate": {
        "udyam reg. number": "udyam_number", "udyam reg number": "udyam_number", "enterprise name": "enterprise_name",
        "major activity": "major_activity", "city": "city", "state": "state", "date of registration": "registration_date",
    },
    "signatory_id": {
        "name": "name", "designation": "designation", "for business": "business", "id no.": "id_no", "id no": "id_no",
        "valid till": "valid_till",
    },
    "address_proof": {
        "consumer no.": "consumer_no", "consumer no": "consumer_no", "billed to": "billed_to",
        "supply address": "address", "bill date": "bill_date", "units consumed": "units", "amount due (inr)": "amount",
    },
}
# second printed line of the address label; contributes no text of its own
_ADDRESS_CONT_LABEL = re.compile(r"^\s*place of business\s*", re.I)
_NOISE = re.compile(r"synthetic|specimen|not a valid|docum|hackathon|fictional|ocr testing|^\W*$", re.I)
# on the ID card, the label sits on its own line and the value on the next
_STACKED = {"signatory_id"}


@dataclass
class Quality:
    sharpness: float
    width: int
    height: int
    ok: bool
    reason: str | None = None


@dataclass
class ExtractedDoc:
    doc_type: str
    fields: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    quality: Quality | None = None
    mean_conf: float = 0.0
    header_ok: bool = True
    used_fallback: bool = False
    skew_deg: float = 0.0


def assess_quality(img_gray: np.ndarray) -> Quality:
    h, w = img_gray.shape[:2]
    sharp = float(cv2.Laplacian(img_gray, cv2.CV_64F).var())
    if min(h, w) < MIN_IMAGE_SIDE_PX:
        return Quality(sharp, w, h, False, "too_small")
    if sharp < BLUR_MIN_LAPLACIAN_VAR:
        return Quality(sharp, w, h, False, "blurry")
    return Quality(sharp, w, h, True)


def estimate_skew(bw: np.ndarray, max_deg: float = 15.0, step: float = 0.5) -> float:
    """Projection-profile skew estimate: the angle whose row sums are 'spikiest' is the one where text lines are level."""
    small = cv2.resize(255 - bw, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
    h, w = small.shape
    best, best_score = 0.0, -1.0
    for a in np.arange(-max_deg, max_deg + step, step):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), float(a), 1.0)
        rows = cv2.warpAffine(small, m, (w, h), flags=cv2.INTER_NEAREST).sum(axis=1).astype(np.float64)
        score = float(np.var(rows))
        if score > best_score:
            best, best_score = float(a), score
    return best


def deskew(bw: np.ndarray) -> tuple[np.ndarray, float]:
    angle = estimate_skew(bw)
    if abs(angle) < 0.75:  # already straight enough
        return bw, 0.0
    h, w = bw.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(bw, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255), angle


def preprocess(img_gray: np.ndarray) -> tuple[np.ndarray, float]:
    """Specimens carry a pale-pink diagonal watermark. A fixed dark threshold keeps the black text and drops it.
    Then straighten photos taken at an angle. Returns (image, skew_angle_applied)."""
    _, bw = cv2.threshold(img_gray, 150, 255, cv2.THRESH_BINARY)
    return deskew(bw)


def _ocr(img: np.ndarray) -> tuple[str, float]:
    cfg = "--psm 6"
    text = pytesseract.image_to_string(img, config=cfg)
    data = pytesseract.image_to_data(img, config=cfg, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c in data["conf"] if str(c) not in ("-1", "")]
    return text, (sum(confs) / len(confs) if confs else 0.0)


def parse_fields(doc_type: str, text: str) -> dict[str, str]:
    labels = _LABELS[doc_type]
    keys = sorted(labels, key=len, reverse=True)  # longest label first ('id no.' before 'name' etc.)
    out: dict[str, str] = {}
    last: str | None = None
    pending: str | None = None  # stacked layout: label seen, waiting for its value line
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _NOISE.search(line):
            continue
        if pending:
            out[pending] = line
            last, pending = pending, None
            continue
        low = line.lower()
        hit = next((k for k in keys if low.startswith(k)), None)
        if hit:
            val = line[len(hit):].strip(" :")
            name = labels[hit]
            if not val and doc_type in _STACKED:
                pending = name
                continue
            out[name] = val
            last = name
        elif doc_type in ("gst_certificate", "address_proof") and last == "address":
            cont = _ADDRESS_CONT_LABEL.sub("", line)
            # certificates wrap mid-word ('Visakhapatnam, A' / 'ndhra Pradesh'): join WITHOUT a space
            out["address"] += cont
    # light clean-ups
    if "address" in out:
        out["address"] = re.sub(r"\s*[-–—~]+\s*(\d{6})\s*$", r" - \1", out["address"]).strip()
    if "udyam_number" in out:
        out["udyam_number"] = re.sub(r"\s+", "", out["udyam_number"])
    return {k: v for k, v in out.items() if v}


def read_document(path: str | Path, doc_type: str,
                  vision_fallback: Callable[[Path, str], dict] | None = None) -> ExtractedDoc:
    path = Path(path)
    assert doc_type in DOC_TYPES, doc_type
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ExtractedDoc(doc_type, quality=Quality(0, 0, 0, False, "unreadable_file"))
    q = assess_quality(img)
    doc = ExtractedDoc(doc_type, quality=q)
    if not q.ok:
        # Do not waste OCR (or leak a blurry personal document to an external model) on an image we will ask to be retaken.
        return doc
    prepped, doc.skew_deg = preprocess(img)
    text, conf = _ocr(prepped)
    doc.raw_text, doc.mean_conf = text, conf
    doc.header_ok = bool(re.search(_HEADERS[doc_type], text, re.I))
    doc.fields = parse_fields(doc_type, text)
    if vision_fallback and (conf < 60 or not doc.fields):
        doc.fields, doc.used_fallback = vision_fallback(path, doc_type), True
    return doc
