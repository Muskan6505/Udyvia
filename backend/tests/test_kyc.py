import json
import re
from datetime import date

import pandas as pd
import pytest

from app.config import DATA_DIR, TODAY
from app.services import registry
from app.services.kyc_decision import run_kyc
from app.services.ocr import DOC_TYPES
from app.services.validators import (correct_gstin_ocr, gstin_checksum_ok, legal_names_match, mask_gstin, names_match,
                                     proprietor_and_trade)


def _paths(k: str) -> dict:
    out = {}
    for t in DOC_TYPES:
        p = DATA_DIR / "kyc_documents" / f"{k}_{t}.png"
        out[t] = p if p.exists() else None
    return out


# ---- end-to-end: the 12 specimen applicants -------------------------------------------------------------------
# decision, codes that MUST be present, gst_products_allowed.   Anything not listed must NOT appear (no false alarms).
EXPECTED = {
    "K01": ("NEEDS_FIX", {"MISSING_FIELD", "GSTIN_CANCELLED"}, False),          # cancelled GSTIN + blank Udyam number
    "K02": ("PASS", set(), True),                                              # photographed at an angle -> deskew
    "K03": ("PASS", set(), True),
    "K04": ("NEEDS_FIX", {"IMAGE_BLURRY"}, False),                             # blurred GST certificate
    "K05": ("NEEDS_FIX", {"MISSING_DOC"}, False),                              # no Udyam certificate
    "K06": ("MANUAL_REVIEW", {"GSTIN_BAD_CHECKSUM"}, False),                   # digit altered on the certificate
    "K07": ("MANUAL_REVIEW", {"GST_NAME_MISMATCH"}, False),                    # 'Shri' vs 'Neelgiri' Physio Clinic
    "K08": ("PASS", set(), True),
    "K09": ("PASS", set(), True),
    "K10": ("PASS", set(), True),
    "K11": ("NEEDS_FIX", {"ADDRESS_PROOF_STALE"}, False),                      # bill dated 2025-10-31
    "K12": ("PASS", set(), True),
}
_INFO_ONLY = {"GSTIN_OCR_CORRECTED"}


@pytest.mark.parametrize("k", sorted(EXPECTED))
def test_specimen_applicant(k):
    decision, must_have, gst_ok = EXPECTED[k]
    r = run_kyc(_paths(k))
    codes = r.codes() - _INFO_ONLY
    assert r.decision == decision, (k, r.decision, [(f.code, f.doc) for f in r.findings])
    assert codes == must_have, (k, codes)
    assert r.gst_products_allowed is gst_ok


def test_no_raw_identifiers_leak_into_output():
    for k in ("K03", "K06", "K09"):
        blob = json.dumps(run_kyc(_paths(k)).to_dict(), ensure_ascii=False)
        reg = pd.read_csv(DATA_DIR / "mock_gstin_registry.csv", dtype=str)
        assert not any(g in blob for g in reg.gstin), "a full GSTIN leaked"
        assert not re.search(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}", blob), "a full Udyam number leaked"


def test_udyam_waiver_turns_missing_doc_into_info():
    paths = _paths("K05")
    r = run_kyc(paths, udyam_waived=True)
    assert "MISSING_DOC" not in r.codes() and "UDYAM_WAIVED" in r.codes()
    assert r.decision == "PASS"


def test_declared_gstin_mismatch_is_flagged():
    r = run_kyc(_paths("K03"), declared_gstin="29FGUXG3354T1ZQ")   # another valid GSTIN
    assert "GSTIN_DECLARED_MISMATCH" in r.codes() and r.decision == "MANUAL_REVIEW"


def test_stale_boundary_is_exactly_90_days():
    # K03's bill is dated 2026-05-30: 46 days before TODAY. Move 'today' to land on day 90 and 91.
    from datetime import timedelta
    bill = date(2026, 5, 30)
    assert "ADDRESS_PROOF_STALE" not in run_kyc(_paths("K03"), today=bill + timedelta(days=90)).codes()
    assert "ADDRESS_PROOF_STALE" in run_kyc(_paths("K03"), today=bill + timedelta(days=91)).codes()


# ---- unit: GSTIN -----------------------------------------------------------------------------------------------
def test_every_registry_gstin_passes_checksum():
    reg = pd.read_csv(DATA_DIR / "mock_gstin_registry.csv", dtype=str)
    assert reg.gstin.map(gstin_checksum_ok).all()


@pytest.mark.parametrize("raw,expected,corrected", [
    ("37ITHKXV5167L1ZS", "37IHKXV5167L1ZS", True),    # one glyph split into two
    ("37THKXV5167L1ZS", "37IHKXV5167L1ZS", True),     # I read as T
    ("27QHIXKO658U1ZL", "27QHJXK0658U1ZL", True),     # J->I and 0->O, two edits
    ("07CPCXNO398P1ZT", "07CPCXN0398P1ZT", True),
    ("32TZAXB5481U1Z1", "32TZAXB5481U1Z1", False),    # already fine
])
def test_ocr_gstin_repair(raw, expected, corrected):
    assert correct_gstin_ocr(raw, exists=registry.gstin_exists) == (expected, corrected)


def test_tampered_gstin_is_not_silently_repaired():
    # K06: certificate says ...S8189... but the registry holds ...S5189.... Must stay invalid, not snap to the registry.
    fixed, _ = correct_gstin_ocr("O8YKZXS8189L1Z0", exists=registry.gstin_exists)
    assert not gstin_checksum_ok(fixed)


def test_mask():
    assert mask_gstin("37IHKXV5167L1ZS") == "37•••••••••L1ZS"
    assert mask_gstin(None) == "—"


# ---- unit: names -----------------------------------------------------------------------------------------------
def test_proprietor_split():
    assert proprietor_and_trade("Neha Banerjee (Prop. Neelgiri Physio Clinic)") == ("Neha Banerjee", "Neelgiri Physio Clinic")
    assert proprietor_and_trade("Balaji Realty LLP") == (None, "Balaji Realty LLP")


def test_one_word_difference_in_long_legal_name_is_caught():
    assert not legal_names_match("Neha Banerjee (Prop. Shri Physio Clinic)", "Neha Banerjee (Prop. Neelgiri Physio Clinic)")


@pytest.mark.parametrize("a,b", [("Harmony Dentay} Care}", "Harmony Dental Care"),
                                 ("Saffron Dental Care LLP", "Saffron Dental Care LLP"),
                                 ("Kaveri Stays LLP", "kaveri  stays llp")])
def test_ocr_noise_and_case_are_tolerated(a, b):
    assert names_match(a, b)
