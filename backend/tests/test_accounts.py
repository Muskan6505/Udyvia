"""Accounts, saved progress and resume, order ownership, and the back-office view."""
import time

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app
from app.privacy import retention
from app.routers import orders
from app.routers import quote as quote_router
from app.services import advisor, journey, propensity
from app.staff import ensure_staff
from test_orders import KIRANA, kyc_session  # noqa: F401  (reuse the KYC helper)

PW = "correct horse battery"


def client() -> TestClient:
    return TestClient(app)


def signup(c, email="asha@example.com", phone="9876543210", consent=True, name="Asha Rao"):
    r = c.post("/auth/register", json=dict(name=name, email=email, phone=phone, password=PW, contact_consent=consent))
    assert r.status_code == 201, r.text
    return r.json()


def chat_to_quote(c):
    sid = None
    for m in ["", "kirana store", "3", "1", "Indore", "no", "cctv and wifi"]:
        r = c.post("/advisor/message", json=dict(message=m, session_id=sid, language="en")).json()
        sid = r["session_id"]
    assert r["quote"], r
    return r


def forget_memory():
    """What a server restart does: the in-memory working state is gone, the database is not."""
    advisor._SESSIONS.clear()
    quote_router._STORE.clear()
    orders._ORDERS.clear()


# ---------- accounts ----------
def test_register_login_logout():
    c = client()
    me = signup(c)
    assert me["role"] == "customer" and c.get("/auth/me").json()["email"] == "asha@example.com"
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401
    assert c.post("/auth/login", json=dict(email="ASHA@example.com", password=PW)).status_code == 200
    assert c.get("/auth/me").status_code == 200


def test_register_validation_and_duplicates():
    c = client()
    bad = dict(name="Asha", email="asha@example.com", phone="9876543210", password=PW)
    assert c.post("/auth/register", json={**bad, "email": "nope"}).status_code == 422
    assert c.post("/auth/register", json={**bad, "phone": "12345"}).status_code == 422
    assert c.post("/auth/register", json={**bad, "password": "short"}).status_code == 422
    signup(c)
    assert client().post("/auth/register", json=bad).status_code == 409


def test_password_is_hashed_and_wrong_password_is_generic():
    c = client()
    signup(c)
    with db.connect() as con:
        stored = con.execute("SELECT pw_hash FROM users").fetchone()[0]
    assert PW not in stored and stored.startswith("scrypt$")
    r = client().post("/auth/login", json=dict(email="asha@example.com", password="wrong password"))
    r2 = client().post("/auth/login", json=dict(email="nobody@example.com", password="wrong password"))
    assert r.status_code == r2.status_code == 401 and r.json() == r2.json()      # same answer: no account enumeration


def test_login_locks_after_repeated_failures():
    signup(client())
    c = client()
    for _ in range(5):
        c.post("/auth/login", json=dict(email="asha@example.com", password="bad bad bad"))
    assert c.post("/auth/login", json=dict(email="asha@example.com", password=PW)).status_code == 429


def test_session_cookie_is_httponly_and_token_is_stored_hashed():
    c = client()
    r = c.post("/auth/register", json=dict(name="Asha", email="a@example.com", phone="9876543210", password=PW))
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=lax" in r.headers["set-cookie"].lower()
    token = c.cookies.get("udyvia_session")
    with db.connect() as con:
        assert token not in [row[0] for row in con.execute("SELECT token_hash FROM sessions")]


def test_expired_session_is_rejected():
    c = client()
    signup(c)
    with db.connect() as con:
        con.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
    assert c.get("/auth/me").status_code == 401


# ---------- saved progress ----------
def test_resume_after_restart_restores_quote_and_addons():
    c = client()
    signup(c)
    r = chat_to_quote(c)
    qid, total = r["quote_id"], r["quote"]["monthly_total"]
    opt = next(l for l in r["quote"]["lines"] if l["role"] != "core" and l["included"])
    c.patch(f"/quote/{qid}/addons", json=dict(product_id=opt["product_id"], included=False))
    new_total = c.get(f"/quote/{qid}").json()["monthly_total"]
    assert new_total < total
    forget_memory()
    res = c.post("/me/resume").json()
    assert res["step"] == "quote" and res["quote"]["monthly_total"] == new_total
    assert res["slots"]["business_type"] == "Kirana store" and res["slots"]["city"] == "Indore"
    # the restored session still works: changing an add-on after resume keeps saving
    res2 = c.patch(f"/quote/{res['quote_id']}/addons", json=dict(product_id=opt["product_id"], included=True)).json()
    assert res2["monthly_total"] == total


def test_resume_partway_through_chat_asks_the_next_question():
    c = client()
    signup(c)
    sid = None
    for m in ["", "kirana store", "3"]:
        r = c.post("/advisor/message", json=dict(message=m, session_id=sid)).json()
        sid = r["session_id"]
    forget_memory()
    res = c.post("/me/resume").json()
    assert res["step"] == "advisor" and res["slots"]["employees"] == 3
    assert "locations" in res["reply"].lower()          # the next unanswered question: how many locations
    r = c.post("/advisor/message", json=dict(message="1", session_id=res["session_id"])).json()
    assert r["slots"]["sites"] == 1


def test_fresh_account_resumes_at_start():
    c = client()
    signup(c)
    res = c.post("/me/resume").json()
    assert res["fresh"] and res["step"] == "advisor" and res["quote"] is None


def test_gstin_is_never_saved_to_the_database():
    c = client()
    signup(c)
    sid = None
    for m in ["", "kirana store", "3", "1", "Indore", "yes my gstin is 27AAPFU0939F1ZV"]:
        r = c.post("/advisor/message", json=dict(message=m, session_id=sid)).json()
        sid = r["session_id"]
    with db.connect() as con:
        blob = " ".join(str(tuple(row)) for row in con.execute("SELECT * FROM journeys"))
    assert "AAPFU0939F" not in blob


def test_restart_clears_progress_but_keeps_account():
    c = client()
    signup(c)
    chat_to_quote(c)
    c.post("/me/restart")
    forget_memory()
    assert c.post("/me/resume").json()["fresh"] and c.get("/auth/me").status_code == 200


def test_another_user_cannot_use_my_advisor_session():
    a, b = client(), client()
    signup(a)
    signup(b, email="b@example.com", phone="9123456780")
    r = a.post("/advisor/message", json=dict(message="")).json()
    assert b.post("/advisor/message", json=dict(message="kirana", session_id=r["session_id"])).status_code == 404


# ---------- orders survive a restart and belong to one account ----------
def place_order(c):
    r = chat_to_quote(c)
    qid = r["quote_id"]
    sid, _ = kyc_session("K03")
    c.post(f"/quote/{qid}/apply-kyc", json={"kyc_session_id": sid})
    o = c.post("/orders", json=dict(quote_id=qid, kyc_session_id=sid))
    assert o.status_code == 201, o.text
    return o.json()["order_id"]


def test_order_resumes_from_database_and_is_private():
    c = client()
    signup(c)
    oid = place_order(c)
    assert c.post("/me/resume").json()["step"] == "sign"
    c.post(f"/orders/{oid}/esign", json=dict(signatory_name="Asha Rao", otp="123456"))
    c.post(f"/orders/{oid}/pay", json=dict(method="upi"))
    forget_memory()
    res = c.post("/me/resume").json()
    assert res["step"] == "track" and res["order"]["status"] == "INSTALL_SCHEDULED"
    assert c.post(f"/orders/{oid}/advance").json()["status"] == "INSTALLED"        # keeps working after the reload
    other = client()
    signup(other, email="b@example.com", phone="9123456780")
    assert other.get(f"/orders/{oid}").status_code == 404
    assert client().get(f"/orders/{oid}").status_code == 404                        # not signed in
    assert journey.get(1)["closed"] == 1


def test_delete_account_erases_everything():
    c = client()
    me = signup(c)
    oid = place_order(c)
    assert c.delete("/auth/account").status_code == 200
    with db.connect() as con:
        for t in ("users", "sessions", "journeys", "orders"):
            assert con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0, t
    assert oid not in orders._ORDERS and c.get("/auth/me").status_code == 401


# ---------- back-office ----------
def staff_client():
    ensure_staff("boss@airtel.example", "a-long-staff-password")
    c = client()
    assert c.post("/auth/login", json=dict(email="boss@airtel.example", password="a-long-staff-password")).status_code == 200
    return c


def test_backoffice_is_staff_only():
    assert client().get("/backoffice/leads").status_code == 401
    c = client()
    signup(c)
    assert c.get("/backoffice/leads").status_code == 403
    assert c.patch("/backoffice/leads/1/follow-up", json=dict(status="called")).status_code == 403


def test_backoffice_lists_open_leads_ranked_and_respects_consent():
    far = client(); signup(far, email="far@example.com", phone="9000000001", name="Far Along")
    chat_to_quote(far)
    sid, _ = kyc_session("K03")                                  # a KYC session is attached to the far lead
    far.post("/kyc/consent", json={"accepted": True})
    near = client(); signup(near, email="near@example.com", phone="9000000002", name="Just Signed")
    nocall = client(); signup(nocall, email="no@example.com", phone="9000000003", name="No Calls", consent=False)
    chat_to_quote(nocall)
    done = client(); signup(done, email="done@example.com", phone="9000000004", name="Customer")
    place = place_order(done)
    done.post(f"/orders/{place}/esign", json=dict(signatory_name="Done Person", otp="123456"))
    done.post(f"/orders/{place}/pay", json=dict(method="upi"))

    r = staff_client().get("/backoffice/leads").json()
    names = [x["name"] for x in r["leads"]]
    assert names == ["Far Along", "Just Signed"]                  # most likely first; closed + opted-out are absent
    assert r["summary"]["opted_out"] == 1 and r["summary"]["open"] == 2
    top = r["leads"][0]
    assert top["stage"] == "kyc" and top["probability"] > r["leads"][1]["probability"]
    assert top["factors"] and top["next_action"] and top["blockers"]
    assert r["model"]["by_stage"]


def test_follow_up_status_is_saved_and_filterable():
    c = client(); signup(c)
    chat_to_quote(c)
    s = staff_client()
    uid = s.get("/backoffice/leads").json()["leads"][0]["id"]
    assert s.patch(f"/backoffice/leads/{uid}/follow-up", json=dict(status="callback", note="Call after 5pm")).status_code == 200
    got = s.get("/backoffice/leads?status=callback").json()["leads"]
    assert got[0]["follow_up_note"] == "Call after 5pm"
    assert s.get("/backoffice/leads?status=new").json()["leads"] == []
    assert s.patch("/backoffice/leads/9999/follow-up", json=dict(status="called")).status_code == 404


def test_blockers_name_the_real_reason():
    c = client(); signup(c)
    chat_to_quote(c)
    sid, res = kyc_session("K04")                                # blurred certificate -> NEEDS_FIX
    uid = 1
    journey.update(uid, "kyc", kyc_decision="NEEDS_FIX")
    lead = staff_client().get("/backoffice/leads").json()["leads"][0]
    assert lead["blockers"][0]["code"] == "KYC_FIX" and "re-upload" in lead["next_action"]


# ---------- propensity model ----------
def f(stage, **kw):
    base = dict(business_type=None, city_tier=None, employees=None, sites=None, has_gstin=None, internet=None)
    return propensity.features(stage=stage, **{**base, **kw})


def test_score_rises_with_stage():
    ps = [propensity.score(f(s))["probability"] for s in propensity.STAGES]
    assert ps == sorted(ps) and ps[-1] > 3 * ps[0]


def test_no_gstin_lowers_the_score_and_says_why():
    with_g = propensity.score(f("Quote accepted", has_gstin=True))
    without = propensity.score(f("Quote accepted", has_gstin=False))
    assert with_g["probability"] > without["probability"]
    assert any(x["feature"] == "GSTIN" and x["direction"] == "down" for x in without["factors"])


def test_unknown_values_are_neutral_and_never_crash():
    a = propensity.score(f("Needs assessed"))
    b = propensity.score(f("Needs assessed", business_type="Alien embassy", internet="Carrier pigeon"))
    assert a["probability"] == b["probability"]


def test_model_ranks_better_than_chance_within_a_stage_on_held_out_leads():
    ev = propensity.evaluate()
    assert all(v["auc"] > 0.55 for v in ev["by_stage"].values()), ev


def test_probabilities_match_history_per_stage():
    rows = propensity._rows()
    for st in propensity.STAGES:
        g = [r for r in rows if r[0]["stage"] == st]
        actual = sum(r[1] for r in g) / len(g)
        predicted = sum(propensity.score(r[0])["probability"] for r in g) / len(g)
        assert abs(actual - predicted) < 0.03, (st, actual, predicted)


# ---------- retention ----------
def test_stale_journeys_are_reset_but_account_stays():
    c = client(); signup(c)
    chat_to_quote(c)
    with db.connect() as con:
        con.execute("UPDATE journeys SET updated=?", (time.time() - 91 * 86400,))
    counts = retention.purge_all()
    assert counts["stale_journeys"] == 1
    assert journey.get(1)["slots"] == {} and c.get("/auth/me").status_code == 200
