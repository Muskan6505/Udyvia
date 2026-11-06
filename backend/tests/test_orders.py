from datetime import date

from fastapi.testclient import TestClient

from app.config import DATA_DIR, TODAY
from app.main import app
from app.services import notify
from app.services.ocr import DOC_TYPES

c = TestClient(app)
KIRANA = dict(business_type="Kirana store", employees=3, sites=1, city_tier=1, has_gstin=False)
TEXTILE = dict(business_type="Textile unit", employees=80, sites=1, city_tier=1, has_gstin=False)


def kyc_session(k):
    sid = c.post("/kyc/consent", json={"accepted": True}).json()["kyc_session_id"]
    for t in DOC_TYPES:
        p = DATA_DIR / "kyc_documents" / f"{k}_{t}.png"
        if p.exists():
            c.post(f"/kyc/{sid}/upload/{t}", files={"file": (p.name, p.read_bytes(), "image/png")})
    return sid, c.post(f"/kyc/{sid}/validate").json()


def place(profile=KIRANA, k="K03", **extra):
    qid = c.post("/quote", json=profile).json()["quote_id"]
    sid, res = kyc_session(k)
    c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid})
    return qid, sid, c.post("/orders", json=dict(quote_id=qid, kyc_session_id=sid, **extra))


def test_order_blocked_until_kyc_passes():
    qid = c.post("/quote", json=KIRANA).json()["quote_id"]
    sid, res = kyc_session("K04")                       # blurred certificate -> NEEDS_FIX
    assert res["decision"] == "NEEDS_FIX"
    r = c.post("/orders", json=dict(quote_id=qid, kyc_session_id=sid))
    assert r.status_code == 409


def test_unknown_quote_or_session():
    assert c.post("/orders", json=dict(quote_id="nope", kyc_session_id="x")).status_code == 404


def test_happy_path_to_activation():
    qid, sid, r = place(contact_phone="+91 98765 43210")
    assert r.status_code == 201
    o = r.json(); oid = o["order_id"]
    assert o["status"] == "KYC_VERIFIED" and o["next_action"] == "Sign your agreement"
    assert o["steps"][0]["state"] == "done" and o["steps"][2]["state"] == "current"
    # cannot pay before signing, wrong OTP rejected
    assert c.post(f"/orders/{oid}/pay", json={}).status_code == 409
    assert c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="000000")).status_code == 400
    r = c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456"))
    assert r.json()["status"] == "ESIGNED"
    assert c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456")).status_code == 409
    r = c.post(f"/orders/{oid}/pay", json=dict(method="upi")).json()
    assert r["status"] == "INSTALL_SCHEDULED"
    assert c.post(f"/orders/{oid}/pay", json={}).status_code == 409        # no double charge
    r = c.post(f"/orders/{oid}/advance").json()
    assert r["status"] == "INSTALLED"
    r = c.post(f"/orders/{oid}/advance").json()
    assert r["status"] == "ACTIVATED" and r["days_to_activation"] == 0
    assert c.post(f"/orders/{oid}/advance").status_code == 409
    assert all(s["state"] == "done" for s in r["steps"])


def test_expected_activation_uses_install_days():
    qid, sid, r = place()                                   # Biz Fibre (5 days) + postpaid (1 day)
    o = r.json(); oid = o["order_id"]
    # sign day+1, pay same day, install +5, activate +1 -> day 7 from TODAY
    assert o["expected_activation"] == str(date.fromordinal(TODAY.toordinal() + 7))
    assert o["days_to_activation"] == 7
    live = {i["product_id"]: i["expected_live_on"] for i in o["items"]}
    assert live["P07"] < live["P01"]                        # the SIM goes live before the fibre


def test_failed_payment_retry_pushes_dates_and_notifies():
    qid, sid, r = place(language="hi")
    o = r.json(); oid = o["order_id"]
    before = c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456")).json()["expected_activation"]
    f = c.post(f"/orders/{oid}/pay", json=dict(simulate_failure=True)).json()
    assert f["status"] == "ESIGNED" and f["payment"]["last_result"] == "failed"
    assert [s for s in f["steps"] if s["code"] == "PAYMENT_RECEIVED"][0]["state"] == "failed"
    assert "retry" in f["help"].lower()
    assert f["expected_activation"] > before                  # honest re-forecast after the lost day
    ok = c.post(f"/orders/{oid}/pay", json=dict(method="card")).json()
    assert ok["status"] == "INSTALL_SCHEDULED" and ok["payment"]["attempts"] == 2
    templates = [n["template"] for n in ok["notifications"]]
    assert templates == ["ORDER_CONFIRMED", "ESIGNED", "PAYMENT_FAILED", "PAYMENT_RECEIVED", "INSTALL_SCHEDULED"]
    assert "ऑर्डर" in ok["notifications"][0]["text"]            # Hindi requested


def test_three_failures_offer_help():
    qid, sid, r = place()
    oid = r.json()["order_id"]
    c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456"))
    for _ in range(2):
        c.post(f"/orders/{oid}/pay", json=dict(simulate_failure=True))
    assert "another" in c.post(f"/orders/{oid}/pay", json=dict(simulate_failure=True)).json()["help"].lower()


def test_phone_is_masked_and_no_identifiers_in_messages():
    qid, sid, r = place(contact_phone="+91 98765 43210")
    o = r.json()
    n = o["notifications"][0]
    assert n["to"] == "••••••••3210" and n["channel"] == "whatsapp"
    assert "98765" not in str(o)
    assert notify.mask_phone("12") is None
    # no phone -> in-app only
    _, _, r2 = place()
    assert r2.json()["notifications"][0]["channel"] == "in_app"


def test_gst_products_need_verified_gstin():
    # K02 passes with an active GSTIN: the textile quote (leased line) can be ordered
    qid, sid, r = place(TEXTILE, "K02")
    assert r.status_code == 201
    names = [i["product_id"] for i in r.json()["items"]]
    assert "P05" in names
    assert r.json()["expected_activation"] > r.json()["steps"][0]["expected_on"]


def test_cancelled_gstin_orders_starter_bundle_only():
    qid, sid, r = place({**TEXTILE, "has_gstin": True}, "K01")   # K01: cancelled GSTIN + missing field -> NEEDS_FIX
    assert r.status_code == 409                                     # cannot order until the fix is made


def test_amount_due_is_first_month_plus_setup():
    qid, sid, r = place()
    o = r.json()
    assert o["amount_due"] == o["monthly_total"] + o["setup_total"]
    assert c.get(f"/orders/{o['order_id']}/tracker").json()["order_id"] == o["order_id"]
    assert c.get("/orders/ORD-NOPE").status_code == 404
