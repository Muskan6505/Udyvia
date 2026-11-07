"""Resume: rebuilds the in-memory working state from what the database saved, and says which screen to open."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import auth
from ..schemas import Profile
from ..services import advisor, journey, slots as sl
from ..services.recommender import assemble
from . import kyc, orders, quote as quote_router

router = APIRouter(prefix="/me", tags=["me"])


def _profile(slots: dict) -> Profile | None:
    s = sl.Slots(**slots)
    if sl.missing(s):
        return None
    tier, _ = sl.tier_for(s.city)
    return Profile(business_type=s.business_type or "", employees=s.employees, sites=s.sites, city=s.city or "", city_tier=tier,
                   gstin=None, has_gstin=s.has_gstin, current_internet=s.current_internet, needs=s.needs,
                   budget_monthly=s.budget_monthly)


@router.get("/journey")
def get_journey(user: dict = Depends(auth.current_user)):
    j = journey.ensure(user["id"])
    return dict(stage=j["stage"], closed=bool(j["closed"]), updated=j["updated"])


@router.post("/resume")
def resume(user: dict = Depends(auth.current_user)):
    j = journey.ensure(user["id"])
    out: dict = dict(stage=j["stage"], lang=j["lang"], step="advisor", fresh=j["stage"] in ("registered",),
                     session_id=None, slots=None, quote=None, quote_id=None, order=None, kyc_session_id=None,
                     kyc_result=None, reply=None, note=None)
    slots = j["slots"]
    if slots:
        s = advisor.restore(slots, j["lang"], user["id"])
        out.update(session_id=s.id, slots=advisor._public_slots(s.slots))
        nxt = sl.next_slot(s.slots)
        out["reply"] = sl.question(nxt, j["lang"]) if nxt else None
    # the quote, rebuilt from the saved profile and the add-ons the person had chosen
    prof = _profile(slots) if slots else None
    if prof and j["selections"]:
        qid = j["quote_id"]
        if qid not in quote_router._STORE:
            quote_router._STORE[qid] = dict(profile=prof, selections=j["selections"], position=j["price_position"] or 0.45,
                                            gst=j["gst_status"], kyc=j["kyc_decision"], created=__import__("time").time(),
                                            user_id=user["id"])
        s_ = quote_router._STORE[qid]
        q, _ = assemble(s_["profile"], s_["selections"], qid, s_["position"], s_.get("gst"), s_.get("kyc"))
        out.update(quote=q.model_dump(), quote_id=qid)
        if out["session_id"]:
            advisor._SESSIONS[out["session_id"]].quote_id = qid
        out["step"] = "quote"
    if j["kyc_session_id"] and j["kyc_session_id"] in kyc._SESSIONS:
        k = kyc._SESSIONS[j["kyc_session_id"]]
        out["kyc_session_id"] = j["kyc_session_id"]
        if k["result"] is not None:
            out["kyc_result"] = k["result"].to_dict()
            out["step"] = "kyc"
        else:
            out["step"] = "kyc"
    elif j["stage"] in ("kyc", "sign", "track") and not j["order_id"]:
        out["step"] = "consent"
        out["note"] = "kyc_expired"          # documents are deleted after 24 hours, so they have to be uploaded again
    if j["order_id"]:
        o = orders.get_owned(j["order_id"], user)
        if o:
            out.update(order=orders._public(o), step="track" if "PAYMENT_RECEIVED" in o["done"] else "sign")
    return out


@router.post("/restart")
def restart(user: dict = Depends(auth.current_user)):
    j = journey.get(user["id"])
    if j and j["kyc_session_id"] in kyc._SESSIONS:
        kyc._purge(j["kyc_session_id"], "restart")
    journey.reset(user["id"])
    return {"ok": True}
