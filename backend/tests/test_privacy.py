import json
import logging
import os
import stat
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import DATA_DIR
from app.main import app
from app.privacy import audit, policy, retention
from app.privacy.logging_filter import ScrubFilter
from app.privacy.masking import contains_identifier, scrub
from app.routers import advisor as _a, kyc as kyc_router, orders, quote as quote_router
from app.services import advisor, data, llm
from app.services.ocr import DOC_TYPES

c = TestClient(app)
PROFILE = dict(business_type="Textile unit", employees=80, sites=1, city_tier=1, has_gstin=False)
GSTIN = "32TTNXB7384T1ZW"


def kyc(k):
    sid = c.post("/kyc/consent", json={"accepted": True}).json()["kyc_session_id"]
    for t in DOC_TYPES:
        p = DATA_DIR / "kyc_documents" / f"{k}_{t}.png"
        if p.exists():
            c.post(f"/kyc/{sid}/upload/{t}", files={"file": (p.name, p.read_bytes(), "image/png")})
    return sid, c.post(f"/kyc/{sid}/validate").json()


# ---------- masking ----------
def test_scrub_masks_each_identifier_type():
    t = f"gst {GSTIN} udyam UDYAM-KL-00-3078801 call +91 98765 43210 mail a.b@x.in id 1234 5678 9012"
    m = scrub(t)
    assert GSTIN not in m and "3078801" not in m and "98765" not in m and "a.b@x.in" not in m and "1234 5678" not in m
    assert m.count("•") > 10 and "3210" in m                      # recognisable stub kept in mask mode
    r = scrub(t, "redact")
    assert "[GSTIN]" in r and "[UDYAM]" in r and "[phone]" in r and "[email]" in r and "[id]" in r
    assert not contains_identifier(r)


def test_scrub_leaves_ordinary_text_and_amounts():
    t = "Total ₹4,316 per month for 10 people, order ORD-1A2B3C4D, install 2026-07-21"
    assert scrub(t) == t


def test_log_filter_scrubs_everything_logged(caplog):
    lg = logging.getLogger("test.privacy")
    lg.addFilter(ScrubFilter())
    with caplog.at_level(logging.INFO, logger="test.privacy"):
        lg.info("lookup for %s by %s", GSTIN, "9876543210")
    assert GSTIN not in caplog.text and "9876543210" not in caplog.text


def test_audit_log_scrubs_even_careless_callers():
    audit.log("oops", "ref1", note=f"typed {GSTIN} and 9876543210", nested=[GSTIN])
    raw = audit.LOG.read_text()
    assert GSTIN not in raw and "9876543210" not in raw


# ---------- nothing sensitive in the audit trail or API output ----------
def test_full_flow_leaves_no_identifiers_in_audit_log():
    qid = c.post("/quote", json=PROFILE).json()["quote_id"]
    sid, res = kyc("K02")
    assert res["decision"] == "PASS"
    c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid})
    o = c.post("/orders", json=dict(quote_id=qid, kyc_session_id=sid, contact_phone="+91 98765 43210")).json()
    oid = o["order_id"]
    c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456"))
    c.post(f"/orders/{oid}/pay", json=dict(method="upi"))
    c.delete(f"/kyc/{sid}")
    raw = audit.LOG.read_text()
    events = [json.loads(l)["event"] for l in raw.splitlines()]
    for e in ["consent_given", "document_uploaded", "kyc_decided", "quote_repriced_after_kyc", "order_created",
              "agreement_signed", "payment_received", "consent_withdrawn", "kyc_data_deleted"]:
        assert e in events, e
    mine = next(r for r in data.gstin_registry().values() if r["trade_name"] == res["autofill"]["trade_name"])
    secrets = ["98765", "Asha", "Rao", mine["gstin"], mine["legal_name"], mine["trade_name"], mine["principal_place_of_business"]]
    assert not [x for x in secrets if x in raw]
    assert not contains_identifier(raw)


def test_kyc_api_output_has_no_raw_identifiers():
    sid, res = kyc("K02")
    blob = json.dumps(res, ensure_ascii=False)
    assert not contains_identifier(blob)
    assert "•" in res["verified"]["gstin"]


# ---------- identifiers never reach the chat model ----------
def test_llm_never_sees_gstin_or_phone(monkeypatch):
    seen = []

    def h(req):
        seen.append(req.content.decode())
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({"employees": 80})}]}}]})

    monkeypatch.setattr(llm, "get_llm", lambda: llm.GeminiClient("k", "m", transport=httpx.MockTransport(h)))
    r = c.post("/advisor/message", json=dict(message=f"Textile unit Surat 80 employees gst {GSTIN} call 98765 43210")).json()
    assert seen and GSTIN not in seen[0] and "98765" not in seen[0] and "[GSTIN]" in seen[0]
    assert r["slots"]["gstin"] == "32•••••••••T1ZW"                # the browser gets it masked
    assert any(x.slots.gstin == GSTIN for x in advisor._SESSIONS.values())      # we validated and kept the real one
    assert any(e["event"] == "llm_input_redacted" for e in audit.read_all())


# ---------- retention ----------
def test_expired_kyc_data_is_deleted_without_anyone_asking():
    sid, _ = kyc("K03")
    d = kyc_router._SESSIONS[sid]["dir"]
    assert d.exists()
    counts = retention.purge_all(now=time.time() + policy.KYC_HOURS * 3600 + 5)
    assert counts["kyc_sessions"] >= 1 and not d.exists() and sid not in kyc_router._SESSIONS
    assert any(e["event"] == "kyc_data_deleted" and e["reason"] == "expired" for e in audit.read_all())


def test_unexpired_data_is_kept():
    sid, _ = kyc("K03")
    retention.purge_all(now=time.time() + 3600)
    assert sid in kyc_router._SESSIONS
    c.delete(f"/kyc/{sid}")


def test_chat_quotes_and_orders_expire_on_their_own_schedules():
    s = advisor.get_session(None, "en")
    qid = c.post("/quote", json=PROFILE).json()["quote_id"]
    sid, _ = kyc("K02")
    c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid})
    oid = c.post("/orders", json=dict(quote_id=qid, kyc_session_id=sid)).json()["order_id"]
    now = time.time()
    retention.purge_all(now=now + 25 * 3600)
    assert s.id not in advisor._SESSIONS and qid in quote_router._STORE and oid in orders._ORDERS
    retention.purge_all(now=now + (policy.QUOTE_HOURS + 1) * 3600)
    assert qid not in quote_router._STORE and oid in orders._ORDERS
    retention.purge_all(now=now + (policy.ORDER_DAYS * 24 + 1) * 3600)
    assert oid not in orders._ORDERS
    c.delete(f"/kyc/{sid}")


@pytest.mark.skipif(os.name == "nt", reason="Windows ignores POSIX permission bits; its per-user temp folder is private by ACL instead")
def test_uploaded_files_are_owner_only():
    sid, _ = kyc("K03")
    d = kyc_router._SESSIONS[sid]["dir"]
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(f.stat().st_mode) == 0o600 for f in d.iterdir())
    c.delete(f"/kyc/{sid}")


def test_policy_endpoint_matches_enforced_constants():
    p = c.get("/privacy/policy").json()
    assert p["retention"]["kyc_documents_and_results_hours"] == policy.KYC_HOURS == kyc_router.RETENTION_SECONDS // 3600
    assert str(policy.KYC_HOURS) in c.get("/kyc/consent").json()["retention"]
    assert "document images" in p["third_parties"][0]["never_receives"]


def test_typed_gstin_is_masked_in_chat_and_quote_responses():
    r = c.post("/advisor/message", json=dict(message=f"Textile unit, Surat, 80 employees, 1 shop, gstin {GSTIN}")).json()
    assert not contains_identifier(json.dumps(r, ensure_ascii=False))
    r = c.post("/advisor/message", json=dict(session_id=r["session_id"], message="no")).json()
    assert r["quote"] and not contains_identifier(json.dumps(r, ensure_ascii=False))
    q = c.get(f"/quote/{r['quote_id']}").json()
    assert q["profile"]["gstin"] == "32•••••••••T1ZW" and not contains_identifier(json.dumps(q))
    assert q["gstin_status"] == "Active"                         # pricing still used the real number
    assert any(l["product_id"] == "P05" and l["included"] for l in q["lines"])


def test_files_left_behind_by_a_restart_are_swept():
    orphan = kyc_router._ROOT / "deadbeef_orphan"
    orphan.mkdir(parents=True, exist_ok=True)
    (orphan / "gst_certificate.png").write_bytes(b"x")
    old = time.time() - 600
    os.utime(orphan, (old, old))
    sid, _ = kyc("K03")                                            # a live session must survive the sweep
    live = kyc_router._SESSIONS[sid]["dir"]
    assert kyc_router.sweep_orphans() >= 1
    assert not orphan.exists() and live.exists()
    c.delete(f"/kyc/{sid}")


def test_fresh_folder_is_not_swept_mid_creation():
    fresh = kyc_router._ROOT / "fresh_folder"
    fresh.mkdir(parents=True, exist_ok=True)
    kyc_router.sweep_orphans(min_age_seconds=60)
    assert fresh.exists()
    kyc_router.sweep_orphans(min_age_seconds=0)
    assert not fresh.exists()


def test_log_filter_keeps_uvicorn_access_records_formattable():
    """uvicorn's access formatter unpacks five arguments; the scrubber must not empty them (it once did)."""
    import logging
    from uvicorn.logging import AccessFormatter
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1234", "GET", "/kyc/27AAPFU0939F1ZV", "1.1", 200), None)
    ScrubFilter().filter(rec)
    line = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s').format(rec)
    assert "27AAPFU0939F1ZV" not in line and "200" in line
