"""Smart KYC orchestration: documents in -> findings + one decision out.

Decision ladder (customer-friendliest first):
  NEEDS_FIX     the customer can resolve it right now (retake photo, upload missing doc, newer bill)
  MANUAL_REVIEW something looks inconsistent or possibly tampered; a human decides
  RESTRICTED    identity is fine but the GSTIN is cancelled/suspended -> GSTIN-gated products are blocked
  PASS          everything checks out
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Callable

from ..config import ADDRESS_PROOF_MAX_AGE_DAYS, TODAY
from . import registry
from .ocr import DOC_TYPES, ExtractedDoc, read_document
from .validators import (UDYAM_RE, addresses_match, clean_udyam, correct_gstin_ocr, gstin_checksum_ok, mask_gstin,
                         legal_names_match, names_match, parse_date, proprietor_and_trade)

FIX, REVIEW, RESTRICT, INFO = "fix", "review", "restrict", "info"

REQUIRED = {
    "gst_certificate": ("gstin", "legal_name", "address"),
    "udyam_certificate": ("udyam_number", "enterprise_name"),
    "signatory_id": ("name", "business", "valid_till"),
    "address_proof": ("billed_to", "address", "bill_date"),
}
DOC_LABEL = {"gst_certificate": "GST certificate", "udyam_certificate": "Udyam certificate",
             "signatory_id": "signatory ID", "address_proof": "address proof"}
FIELD_LABEL = {"udyam_number": "Udyam number", "gstin": "GSTIN", "legal_name": "legal name", "address": "address",
               "enterprise_name": "enterprise name", "name": "name", "business": "business name",
               "valid_till": "validity date", "billed_to": "billed-to name", "bill_date": "bill date"}


@dataclass
class Finding:
    code: str
    severity: str               # fix | review | restrict | info
    doc: str | None
    message: str                # plain-language, safe to show to the customer (never contains raw identifiers)


@dataclass
class KycResult:
    decision: str
    findings: list[Finding] = field(default_factory=list)
    gst_products_allowed: bool = False
    verified: dict = field(default_factory=dict)   # masked identifiers + verification flags
    autofill: dict = field(default_factory=dict)   # registry data the UI can pre-fill after consent

    def codes(self) -> set[str]:
        return {f.code for f in self.findings}

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _add(fs: list[Finding], code: str, sev: str, doc: str | None, msg: str) -> None:
    fs.append(Finding(code, sev, doc, msg))


def run_kyc(paths: dict[str, str | Path | None], *, today: date = TODAY, declared_gstin: str | None = None,
            udyam_waived: bool = False,
            vision_fallback: Callable[[Path, str], dict] | None = None) -> KycResult:
    """paths: {doc_type: image path or None}. `udyam_waived` = owner states they have no Udyam registration."""
    fs: list[Finding] = []
    docs: dict[str, ExtractedDoc] = {}

    # ---- 1. completeness, quality, readability -------------------------------------------------
    for t in DOC_TYPES:
        p = paths.get(t)
        if not p:
            if t == "udyam_certificate" and udyam_waived:
                _add(fs, "UDYAM_WAIVED", INFO, t, "You told us you don't have a Udyam registration. We'll continue without it.")
            else:
                extra = " Or tell us you don't have one." if t == "udyam_certificate" else ""
                _add(fs, "MISSING_DOC", FIX, t, f"Please upload your {DOC_LABEL[t]}.{extra}")
            continue
        d = read_document(p, t, vision_fallback)
        docs[t] = d
        q = d.quality
        if q and not q.ok:
            msg = {"blurry": f"Your {DOC_LABEL[t]} photo is too blurry to read. Please retake it in good light, holding the phone steady.",
                   "too_small": f"Your {DOC_LABEL[t]} image is too small. Please upload a larger photo.",
                   "unreadable_file": f"We couldn't open your {DOC_LABEL[t]} file. Please upload it again."}[q.reason]
            _add(fs, "IMAGE_" + q.reason.upper(), FIX, t, msg)
            continue
        if not d.header_ok:
            _add(fs, "WRONG_DOC_TYPE", FIX, t, f"This doesn't look like a {DOC_LABEL[t]}. Please upload the right document.")
            continue
        for f in REQUIRED[t]:
            if not d.fields.get(f):
                _add(fs, "MISSING_FIELD", FIX, t,
                     f"We couldn't find the {FIELD_LABEL[f]} on your {DOC_LABEL[t]}. Please upload a complete, clear copy.")

    gst, udy, sid, adr = (docs.get(t) for t in DOC_TYPES)
    gst_f = gst.fields if gst and gst.quality.ok else {}
    udy_f = udy.fields if udy and udy.quality.ok else {}
    sid_f = sid.fields if sid and sid.quality.ok else {}
    adr_f = adr.fields if adr and adr.quality.ok else {}

    # ---- 2. GSTIN: checksum -> registry -> status ---------------------------------------------
    reg_g = None
    gstin = None
    gst_ok = False
    if gst_f.get("gstin"):
        gstin, corrected = correct_gstin_ocr(gst_f["gstin"], exists=registry.gstin_exists)
        if not gstin_checksum_ok(gstin or ""):
            _add(fs, "GSTIN_BAD_CHECKSUM", REVIEW, "gst_certificate",
                 "The GSTIN on your certificate isn't a valid GSTIN. Our team will check it with you.")
            gstin = None
        else:
            if corrected:
                _add(fs, "GSTIN_OCR_CORRECTED", INFO, "gst_certificate", "Fixed a small reading error in the GSTIN (checksum-verified).")
            reg_g = registry.lookup_gstin(gstin)
            if not reg_g:
                _add(fs, "GSTIN_NOT_IN_REGISTRY", REVIEW, "gst_certificate",
                     "We couldn't find this GSTIN in the GST registry. Our team will check it with you.")
            elif reg_g["status"] != "Active":
                st = reg_g["status"].lower()
                _add(fs, f"GSTIN_{st.upper()}", RESTRICT, "gst_certificate",
                     f"This GSTIN is {st} in the GST registry. You can continue with products that don't need a GSTIN; "
                     f"GST-based products unlock once your registration is active again.")
            else:
                gst_ok = True
        if declared_gstin and gstin and declared_gstin.strip().upper() != gstin:
            _add(fs, "GSTIN_DECLARED_MISMATCH", REVIEW, "gst_certificate",
                 "The GSTIN you typed differs from the one on your certificate.")

    # ---- 3. GST certificate vs registry --------------------------------------------------------
    anchor_name = None  # the trading name every other document is compared with
    if reg_g:
        anchor_name = reg_g["trade_name"]
        if not legal_names_match(gst_f.get("legal_name"), reg_g["legal_name"]):
            _add(fs, "GST_NAME_MISMATCH", REVIEW, "gst_certificate",
                 "The business name on your GST certificate doesn't match the GST registry.")
        if gst_f.get("trade_name") and not names_match(gst_f["trade_name"], reg_g["trade_name"]):
            _add(fs, "GST_NAME_MISMATCH", REVIEW, "gst_certificate",
                 "The trade name on your GST certificate doesn't match the GST registry.")
        if gst_f.get("address") and not addresses_match(gst_f["address"], reg_g["principal_place_of_business"]):
            _add(fs, "GST_ADDRESS_MISMATCH", REVIEW, "gst_certificate",
                 "The address on your GST certificate doesn't match the GST registry.")
    elif gst_f.get("trade_name"):
        anchor_name = gst_f["trade_name"]
    anchor_addr = reg_g["principal_place_of_business"] if reg_g else gst_f.get("address")

    # ---- 4. Udyam ------------------------------------------------------------------------------
    udyam_no = clean_udyam(udy_f.get("udyam_number"))
    reg_u = None
    if udy and udy.quality.ok and "udyam_number" in udy_f:
        if not UDYAM_RE.fullmatch(udyam_no or ""):
            _add(fs, "UDYAM_BAD_FORMAT", FIX, "udyam_certificate",
                 "The Udyam number on your certificate isn't in the right format. Please upload a clearer copy.")
        else:
            reg_u = registry.lookup_udyam(udyam_no)
            if not reg_u:
                _add(fs, "UDYAM_NOT_IN_REGISTRY", REVIEW, "udyam_certificate",
                     "We couldn't find this Udyam number in the Udyam registry. Our team will check it with you.")
            elif not names_match(udy_f.get("enterprise_name"), reg_u["enterprise_name"]):
                _add(fs, "UDYAM_NAME_MISMATCH", REVIEW, "udyam_certificate",
                     "The enterprise name on your Udyam certificate doesn't match the Udyam registry.")
    if reg_u and not anchor_name:
        anchor_name = reg_u["enterprise_name"]

    # ---- 5. Signatory ID -----------------------------------------------------------------------
    if sid_f.get("valid_till"):
        vt = parse_date(sid_f["valid_till"])
        if vt and vt < today:
            _add(fs, "ID_EXPIRED", FIX, "signatory_id", "Your signatory ID has expired. Please upload a valid one.")
    if sid_f.get("business") and anchor_name and not names_match(sid_f["business"], anchor_name):
        _add(fs, "ID_BUSINESS_MISMATCH", REVIEW, "signatory_id", "The business named on the signatory ID doesn't match your registration.")
    legal = reg_g["legal_name"] if reg_g else gst_f.get("legal_name")
    proprietor, _ = proprietor_and_trade(legal)
    if proprietor and sid_f.get("name") and not names_match(sid_f["name"], proprietor):
        _add(fs, "SIGNATORY_NOT_PROPRIETOR", REVIEW, "signatory_id",
             "The signatory's name doesn't match the proprietor on the GST registration.")

    # ---- 6. Address proof ----------------------------------------------------------------------
    if adr_f.get("bill_date"):
        bd = parse_date(adr_f["bill_date"])
        if bd is None:
            _add(fs, "MISSING_FIELD", FIX, "address_proof", "We couldn't read the bill date. Please upload a clearer copy.")
        elif bd > today:
            _add(fs, "ADDRESS_PROOF_FUTURE", REVIEW, "address_proof", "The bill is dated in the future. Our team will check it with you.")
        elif (today - bd).days > ADDRESS_PROOF_MAX_AGE_DAYS:
            _add(fs, "ADDRESS_PROOF_STALE", FIX, "address_proof",
                 f"Your address proof is older than {ADDRESS_PROOF_MAX_AGE_DAYS} days. Please upload a more recent bill.")
    if adr_f.get("billed_to") and anchor_name and not names_match(adr_f["billed_to"], anchor_name):
        _add(fs, "ADDRESS_PROOF_NAME_MISMATCH", REVIEW, "address_proof", "The name on the bill doesn't match your business registration.")
    if adr_f.get("address") and anchor_addr and not addresses_match(adr_f["address"], anchor_addr):
        _add(fs, "ADDRESS_PROOF_ADDRESS_MISMATCH", REVIEW, "address_proof", "The address on the bill doesn't match your registered address.")

    # ---- 7. Udyam enterprise name vs the other documents (cross-check) ------------------------
    if udy_f.get("enterprise_name") and anchor_name and not names_match(udy_f["enterprise_name"], anchor_name) \
            and "UDYAM_NAME_MISMATCH" not in {f.code for f in fs}:
        _add(fs, "UDYAM_NAME_MISMATCH", REVIEW, "udyam_certificate", "The name on your Udyam certificate doesn't match your GST registration.")

    # ---- decision ------------------------------------------------------------------------------
    sev = {f.severity for f in fs}
    decision = ("NEEDS_FIX" if FIX in sev else "MANUAL_REVIEW" if REVIEW in sev else "RESTRICTED" if RESTRICT in sev else "PASS")
    allowed = gst_ok and decision in ("PASS",)
    res = KycResult(decision, fs, gst_products_allowed=allowed)
    res.verified = {"gstin": mask_gstin(gstin), "gstin_status": reg_g["status"] if reg_g else None,
                    "udyam": (udyam_no[:8] + "•••" + udyam_no[-3:]) if udyam_no else None, "udyam_in_registry": bool(reg_u)}
    if reg_g:
        res.autofill = {"legal_name": reg_g["legal_name"], "trade_name": reg_g["trade_name"],
                        "address": reg_g["principal_place_of_business"], "state": reg_g["state"],
                        "constitution": reg_g["constitution"]}
    return res
