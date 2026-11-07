"""Back-office view for Airtel sales and channel partners: the leads the advisor did not close, ranked by
how likely each is to activate if someone calls. Staff accounts only; every view is audit-logged."""
from __future__ import annotations

import time
from functools import lru_cache
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth, db
from ..privacy import audit
from ..services import journey, propensity, slots as sl

router = APIRouter(prefix="/backoffice", tags=["backoffice"])


def hist_stage(j: dict) -> str:
    """Map where a live lead is to the stage names in the historical data the model learnt from."""
    st = j["stage"]
    if st == "registered":
        return "Lead"
    if st == "advisor":
        return "Contacted"
    if st == "quote":
        return "Needs assessed"
    if st == "kyc":
        return "KYC complete" if j["kyc_decision"] in ("PASS", "RESTRICTED") else "Quote accepted"
    return "KYC complete"


STAGE_TEXT = {
    "registered": "Signed up but never started the chat",
    "advisor": "Left the chat before getting a quote",
    "quote": "Has a quote but hasn't started KYC",
    "kyc": "Started KYC but didn't finish",
    "sign": "Placed the order but didn't sign or pay",
}


def blockers(j: dict) -> list[dict]:
    """Plain rule-based reasons the lead stalled, most useful first. Shown beside the score, not part of it."""
    out = []
    kd = j["kyc_decision"]
    if kd == "RESTRICTED":
        out.append(dict(code="GSTIN_RESTRICTED", text="GSTIN is cancelled or suspended; only the starter bundle applies",
                        action="Offer the GSTIN-free starter bundle and explain how to re-activate the GSTIN"))
    if kd == "NEEDS_FIX":
        out.append(dict(code="KYC_FIX", text="KYC documents need fixing (blurry, expired or mismatched)",
                        action="Call to help them re-upload clear documents"))
    if kd == "MANUAL_REVIEW":
        out.append(dict(code="KYC_REVIEW", text="KYC is waiting for a manual review", action="Check the review queue, then update the customer"))
    if j["payment_failures"] and not j["closed"]:
        out.append(dict(code="PAYMENT", text=f"Payment failed {j['payment_failures']} time(s)", action="Offer another payment method or take payment over the phone"))
    if j["within_budget"] == 0:
        out.append(dict(code="BUDGET", text="Quote is above the budget they gave", action="Offer a lower tier or fewer add-ons"))
    if j["blocked_count"]:
        out.append(dict(code="BLOCKED", text=f"{j['blocked_count']} product(s) they wanted can't be offered yet", action="Explain the upgrade path (for example GSTIN or more staff)"))
    out.append(dict(code="STAGE", text=STAGE_TEXT.get(j["stage"], "Open"), action={
        "registered": "Call to understand what they need", "advisor": "Call to finish the questions the advisor asked",
        "quote": "Call to walk through the quote and what KYC needs", "kyc": "Call to help finish KYC",
        "sign": "Call to help with e-sign and payment"}.get(j["stage"], "Follow up")))
    return out


def lead_row(u: dict, j: dict, now: float) -> dict:
    s = sl.Slots(**{**j["slots"], "gstin": None}) if j["slots"] else sl.Slots()
    tier = sl.tier_for(s.city)[0] if s.city else None
    feat = propensity.features(stage=hist_stage(j), business_type=s.business_type, city_tier=tier, employees=s.employees,
                               sites=s.sites, has_gstin=s.has_gstin, internet=s.current_internet)
    sc = propensity.score(feat)
    b = blockers(j)
    value = j["monthly_total"] or 0
    return dict(
        id=u["id"], name=u["name"], phone=u["phone"], email=u["email"], demo=bool(u["is_demo"]),
        business=s.business_type, city=s.city, employees=s.employees, sites=s.sites, segment=j["segment"],
        stage=j["stage"], stage_text=STAGE_TEXT.get(j["stage"], "Open"), kyc_decision=j["kyc_decision"],
        monthly_total=j["monthly_total"], idle_minutes=int((now - j["updated"]) // 60),
        probability=sc["probability"], band=propensity.band(sc["probability"]), factors=sc["factors"],
        expected_value=round(sc["probability"] * value), blockers=b[:3], next_action=b[0]["action"],
        follow_up_status=j["follow_up_status"], follow_up_note=j["follow_up_note"], followed_up_at=j["followed_up_at"])


@lru_cache(maxsize=1)
def _model_card() -> dict:
    ev = propensity.evaluate()
    return dict(trained_on="5,000 historical leads", **ev,
                note="Within each stage the score ranks eventual winners above losers better than chance (AUC 0.5 = a coin toss), "
                     "but only modestly. Use it to order a call list, not to rule anyone out.")


@router.get("/leads")
def leads(band: Literal["all", "Hot", "Warm", "Cold"] = "all", sort: Literal["score", "value"] = "score",
          min_idle_minutes: int = 0, status: str = "all", staff: dict = Depends(auth.staff_user)):
    now = time.time()
    with db.connect() as c:
        rows = c.execute("SELECT u.*, j.user_id AS j_user FROM users u JOIN journeys j ON j.user_id=u.id "
                         "WHERE u.role='customer' AND j.closed=0").fetchall()
        users = {r["id"]: dict(r) for r in rows}
    out, opted_out = [], 0
    for uid, u in users.items():
        if not u["contact_consent"]:
            opted_out += 1                       # these people said not to call: they are counted, never listed
            continue
        j = journey.get(uid)
        row = lead_row(u, j, now)
        if row["idle_minutes"] < min_idle_minutes or (band != "all" and row["band"] != band):
            continue
        if status != "all" and row["follow_up_status"] != status:
            continue
        out.append(row)
    out.sort(key=lambda r: -(r["probability"] if sort == "score" else r["expected_value"]))
    audit.log("backoffice_leads_viewed", str(staff["id"]), shown=len(out), opted_out=opted_out)
    summary = dict(open=len(out), hot=sum(r["band"] == "Hot" for r in out), warm=sum(r["band"] == "Warm" for r in out),
                   cold=sum(r["band"] == "Cold" for r in out), opted_out=opted_out,
                   expected_monthly_value=sum(r["expected_value"] for r in out))
    return dict(leads=out, summary=summary, model=_model_card())


class FollowUp(BaseModel):
    status: Literal["new", "called", "callback", "not_interested"]
    note: str = Field(default="", max_length=300)


@router.patch("/leads/{uid}/follow-up")
def follow_up(uid: int, body: FollowUp, staff: dict = Depends(auth.staff_user)):
    with db.connect() as c:
        u = c.execute("SELECT id FROM users WHERE id=? AND role='customer' AND contact_consent=1", (uid,)).fetchone()
        if not u:
            raise HTTPException(404, "lead not found")
        c.execute("UPDATE journeys SET follow_up_status=?, follow_up_note=?, followed_up_at=? WHERE user_id=?",
                  (body.status, body.note.strip(), time.time(), uid))
    audit.log("lead_follow_up", str(staff["id"]), lead=uid, status=body.status)
    return {"ok": True}
