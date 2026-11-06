from fastapi.testclient import TestClient

from app.config import DATA_DIR
from app.main import app
from app.services.ocr import DOC_TYPES

c = TestClient(app)
GATED_PROFILE = dict(business_type="Textile unit", employees=80, sites=1, city_tier=1, has_gstin=False)


def _run(k, upload=True):
    sid = c.post("/kyc/consent", json={"accepted": True}).json()["kyc_session_id"]
    for t in DOC_TYPES:
        p = DATA_DIR / "kyc_documents" / f"{k}_{t}.png"
        if p.exists():
            r = c.post(f"/kyc/{sid}/upload/{t}", files={"file": (p.name, p.read_bytes(), "image/png")})
            assert r.status_code == 200
    return sid, c.post(f"/kyc/{sid}/validate").json()


def test_consent_required():
    assert c.post("/kyc/consent", json={"accepted": False}).status_code == 400
    assert c.post("/kyc/nope/upload/gst_certificate", files={"file": ("a.png", b"x", "image/png")}).status_code == 404


def test_upload_rejects_non_images_and_bad_type():
    sid = c.post("/kyc/consent", json={"accepted": True}).json()["kyc_session_id"]
    assert c.post(f"/kyc/{sid}/upload/gst_certificate", files={"file": ("a.pdf", b"x", "application/pdf")}).status_code == 415
    assert c.post(f"/kyc/{sid}/upload/passport", files={"file": ("a.png", b"x", "image/png")}).status_code == 422


def test_pass_unlocks_gst_products_in_quote():
    sid, res = _run("K02")
    assert res["decision"] == "PASS"
    q = c.post("/quote", json=GATED_PROFILE).json()
    assert not any(l["product_id"] == "P05" for l in q["lines"])
    qid = c.post("/quote", json=GATED_PROFILE).json()["quote_id"]
    r = c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid}).json()
    assert r["gstin_status"] == "Active"
    assert any(l["product_id"] == "P05" and l["included"] for l in r["lines"])   # leased line unlocked


def test_cancelled_gstin_forces_starter_bundle():
    sid, res = _run("K01")
    assert "GSTIN_CANCELLED" in {f["code"] for f in res["findings"]}
    qid = c.post("/quote", json={**GATED_PROFILE, "has_gstin": True}).json()["quote_id"]
    r = c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid}).json()
    assert r["gstin_status"] == "Cancelled"
    assert not any(l["product_id"] == "P05" and l["included"] for l in r["lines"])


def test_apply_requires_validated_session():
    sid = c.post("/kyc/consent", json={"accepted": True}).json()["kyc_session_id"]
    qid = c.post("/quote", json=GATED_PROFILE).json()["quote_id"]
    assert c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid}).status_code == 409


def test_withdraw_deletes_files():
    sid, _ = _run("K03")
    from app.routers.kyc import _SESSIONS
    d = _SESSIONS[sid]["dir"]
    assert any(d.iterdir())
    assert c.delete(f"/kyc/{sid}").json() == {"deleted": True}
    assert not d.exists()
    assert c.get(f"/kyc/{sid}/result").status_code == 404
