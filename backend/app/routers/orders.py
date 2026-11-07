"""Orders: quote -> order -> e-sign (mock) -> payment (mock, with retry) -> install -> active."""
from __future__ import annotations

import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import auth
from ..config import TODAY
from ..privacy import audit
from ..services import data, journey, notify, tracker
from . import kyc, quote as quote_router

router = APIRouter(prefix="/orders", tags=["orders"])
_ORDERS: dict[str, dict] = {}

DEMO_OTP = "123456"            # mock e-sign OTP: a real build would call an e-sign provider
MAX_PAYMENT_ATTEMPTS_BEFORE_HELP = 3


class OrderIn(BaseModel):
    quote_id: str
    kyc_session_id: str
    language: Literal["en", "hi"] = "en"
    contact_phone: str | None = None


class EsignIn(BaseModel):
    signatory_name: str = Field(min_length=2, max_length=80)
    otp: str


class PayIn(BaseModel):
    method: Literal["upi", "card", "netbanking"] = "upi"
    simulate_failure: bool = False      # demo switch for the "first payment failed" path


def get_owned(oid: str, user: dict | None) -> dict | None:
    """The order, from memory or the database. An order that belongs to an account is visible only to that account."""
    o = _ORDERS.get(oid)
    if o is None:
        loaded = journey.load_order(oid)
        if loaded:
            o, uid = loaded
            o["user_id"] = uid
            _ORDERS[oid] = o
    if o is None:
        return None
    if o.get("user_id") and (not user or user["id"] != o["user_id"]):
        return None
    return o


def _get(oid: str, user: dict | None = None) -> dict:
    o = get_owned(oid, user)
    if not o:
        raise HTTPException(404, "order not found")
    return o


def _save(o: dict) -> None:
    """Write-through to the database for orders that belong to an account, and keep the journey current."""
    uid = o.get("user_id")
    if not uid:
        return
    journey.save_order(uid, o)
    won = "PAYMENT_RECEIVED" in o["done"]
    journey.update(uid, "track" if won else "sign", order_id=o["order_id"], closed=int(won),
                   payment_failures=o["payment"]["attempts"] - (1 if o["payment"]["last_result"] == "success" else 0))


def _step(o: dict, code: str, **notif) -> None:
    o["done"][code] = o["clock"]
    o["status"] = code
    if notif.get("template"):
        notify.send(o["notifications"], language=o["language"], on=str(o["clock"]),
                    phone_masked=o["phone_masked"], oid=o["order_id"], **notif)


def _public(o: dict) -> dict:
    t = tracker.timeline(o)
    t.update(amount_due=o["amount_due"], monthly_total=o["monthly_total"], setup_total=o["setup_total"],
             contract_months=o["contract_months"], payment=dict(o["payment"]))
    return t


@router.post("", status_code=201)
def create_order(body: OrderIn, user: dict | None = Depends(auth.optional_user)):
    qs = quote_router._STORE.get(body.quote_id)
    if not qs:
        raise HTTPException(404, "quote not found")
    k = kyc.get_session(body.kyc_session_id)
    res = k["result"]
    if res is None or res.decision not in ("PASS", "RESTRICTED"):
        raise HTTPException(409, "KYC must be completed (PASS) before an order can be placed")
    q = quote_router.get_quote(body.quote_id)
    inc = [l for l in q.lines if l.included]
    if not inc:
        raise HTTPException(409, "the quote has no products selected")
    cat = data.catalogue()
    if any(cat[l.product_id].requires_gstin for l in inc) and not res.gst_products_allowed:
        raise HTTPException(409, "this quote has GSTIN-based products but the GSTIN isn't verified as active")
    oid = "ORD-" + uuid.uuid4().hex[:8].upper()
    o = dict(order_id=oid, quote_id=body.quote_id, language=body.language, clock=TODAY, status="KYC_VERIFIED",
             phone_masked=notify.mask_phone(body.contact_phone), notifications=[],
             items=[dict(product_id=l.product_id, product_name=l.product_name, qty=l.qty) for l in inc],
             monthly_total=q.monthly_total, setup_total=q.setup_total, contract_months=q.contract_months,
             amount_due=q.monthly_total + q.setup_total,       # first month in advance + one-time setup
             done={}, signed_by=None, created=time.time(), payment=dict(attempts=0, last_result=None, method=None))
    o["done"]["QUOTE_ACCEPTED"] = TODAY
    _step(o, "KYC_VERIFIED", template="ORDER_CONFIRMED")
    if user:
        o["user_id"] = user["id"]
    _ORDERS[oid] = o
    _save(o)
    audit.log("order_created", oid, quote_id=body.quote_id, items=len(inc), phone_given=bool(o["phone_masked"]))
    return _public(o)


@router.get("/{oid}")
def get_order(oid: str, user: dict | None = Depends(auth.optional_user)):
    return _public(_get(oid, user))


@router.get("/{oid}/tracker")
def get_tracker(oid: str, user: dict | None = Depends(auth.optional_user)):
    return tracker.timeline(_get(oid, user))


@router.post("/{oid}/esign")
def esign(oid: str, body: EsignIn, user: dict | None = Depends(auth.optional_user)):
    o = _get(oid, user)
    if "ESIGNED" in o["done"]:
        raise HTTPException(409, "already signed")
    if body.otp != DEMO_OTP:
        raise HTTPException(400, "That code didn't match. Please check the OTP and try again")
    o["signed_by"] = body.signatory_name.strip()
    _step(o, "ESIGNED", template="ESIGNED", amount=f"{o['amount_due']:,}")
    _save(o)
    audit.log("agreement_signed", oid)         # the signatory's name is stored on the order, never in logs
    return _public(o)


@router.post("/{oid}/pay")
def pay(oid: str, body: PayIn, user: dict | None = Depends(auth.optional_user)):
    o = _get(oid, user)
    if "ESIGNED" not in o["done"]:
        raise HTTPException(409, "please sign the agreement first")
    if "PAYMENT_RECEIVED" in o["done"]:
        raise HTTPException(409, "payment already received")     # no double charge
    p = o["payment"]
    p["attempts"] += 1
    p["method"] = body.method
    if body.simulate_failure:
        audit.log("payment_failed", oid, attempt=p["attempts"], method=body.method)
        p["last_result"] = "failed"
        o["clock"] = o["clock"].fromordinal(o["clock"].toordinal() + 1)    # a failed attempt costs a day
        notify.send(o["notifications"], template="PAYMENT_FAILED", language=o["language"], on=str(o["clock"]),
                    phone_masked=o["phone_masked"], oid=oid)
        _save(o)
        out = _public(o)
        out["help"] = ("Still stuck? Try another payment method or ask us to call you."
                       if p["attempts"] >= MAX_PAYMENT_ATTEMPTS_BEFORE_HELP else "Nothing was charged. You can retry.")
        return out
    p["last_result"] = "success"
    audit.log("payment_received", oid, attempt=p["attempts"], method=body.method, amount=o["amount_due"])
    _step(o, "PAYMENT_RECEIVED", template="PAYMENT_RECEIVED", amount=f"{o['amount_due']:,}")
    _step(o, "INSTALL_SCHEDULED", template="INSTALL_SCHEDULED", date=tracker.expected_dates(o)["INSTALLED"].strftime("%d %b %Y"))
    _save(o)
    return _public(o)


@router.post("/{oid}/advance")
def advance(oid: str, user: dict | None = Depends(auth.optional_user)):
    """DEMO ONLY: moves the simulated clock to the next milestone (install done, then active)."""
    o = _get(oid, user)
    if "INSTALL_SCHEDULED" not in o["done"]:
        raise HTTPException(409, "installation hasn't been scheduled yet (sign and pay first)")
    exp = tracker.expected_dates(o)
    if "INSTALLED" not in o["done"]:
        o["clock"] = max(o["clock"], exp["INSTALLED"])
        _step(o, "INSTALLED", template="INSTALLED")
    elif "ACTIVATED" not in o["done"]:
        o["clock"] = max(o["clock"], exp["ACTIVATED"])
        _step(o, "ACTIVATED", template="ACTIVATED")
    else:
        raise HTTPException(409, "already active")
    _save(o)
    return _public(o)
