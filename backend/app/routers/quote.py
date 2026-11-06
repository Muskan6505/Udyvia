from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..schemas import AddonChange, Profile, Quote
from ..services import data
from ..privacy import audit
from . import kyc
from ..services import eligibility as el
from ..services.recommender import assemble, default_qty, classify_seg

router = APIRouter(prefix="/quote", tags=["quote"])
_STORE: dict[str, dict] = {}   # quote_id -> {profile, selections, position}


@router.post("", response_model=Quote)
def create_quote(profile: Profile):
    q, sel = assemble(profile)
    _STORE[q.quote_id] = dict(profile=profile, selections=sel, position=q.price_position, gst=None, kyc=None, created=time.time())
    return q


@router.get("/{quote_id}", response_model=Quote)
def get_quote(quote_id: str):
    s = _STORE.get(quote_id)
    if not s:
        raise HTTPException(404, "quote not found")
    q, _ = assemble(s["profile"], s["selections"], quote_id, s["position"], s.get("gst"), s.get("kyc"))
    return q


@router.patch("/{quote_id}/addons", response_model=Quote)
def change_addon(quote_id: str, change: AddonChange):
    s = _STORE.get(quote_id)
    if not s:
        raise HTTPException(404, "quote not found")
    cat = data.catalogue()
    if change.product_id not in cat:
        raise HTTPException(422, "unknown product")
    sel = {k: dict(v) for k, v in s["selections"].items()}
    cur = sel.get(change.product_id)
    if cur is None:
        if not change.included:
            return get_quote(quote_id)
        # not in the offered list: adding runs the same eligibility checks
        cur = dict(included=True, qty=default_qty(change.product_id, s["profile"], classify_seg(s["profile"])),
                   role="addon", reason="Added by you")
        sel[change.product_id] = cur
    cur["included"] = change.included
    if change.qty:
        cur["qty"] = change.qty
    if not change.included:
        # removing a connection also switches off what depends on it (no silent re-adding)
        inc = {k for k, v in sel.items() if v["included"]}
        for pid, v in sel.items():
            if v["included"] and not el.dependency_met(cat[pid], inc):
                v["included"] = False
    q, new_sel = assemble(s["profile"], sel, quote_id, s["position"], s.get("gst"), s.get("kyc"))
    # cascade: connectivity removal drops dependents (handled by assemble's dependency pass)
    if change.included and change.product_id not in new_sel:
        q.notes.append("That product can't be added to this bundle; see 'blocked'.")
    s["selections"] = new_sel
    return q


def apply_kyc_result(quote_id: str, res) -> Quote | None:
    """Feed a KYC outcome into a quote: a cancelled/suspended GSTIN (or a verified active one) replaces the claim.

    Re-derives the bundle from the profile so GSTIN-gated lines drop out (and the starter bundle appears)."""
    s = _STORE.get(quote_id)
    if not s:
        return None
    st = res.verified.get("gstin_status")
    if st in ("Cancelled", "Suspended") or (st == "Active" and res.decision == "PASS"):
        s["gst"] = st
    s["kyc"] = res.decision
    audit.log("quote_repriced_after_kyc", quote_id, decision=res.decision, gstin_status=s.get("gst"))
    q, sel = assemble(s["profile"], None, quote_id, s["position"], s["gst"], s["kyc"])
    s["selections"] = sel
    return q


class KycLink(BaseModel):
    kyc_session_id: str


@router.post("/{quote_id}/apply-kyc", response_model=Quote)
def apply_kyc(quote_id: str, body: KycLink):
    """Re-prices using the registry-verified GSTIN status from Smart KYC. The status comes from the
    server-side KYC session, never from the client, so it can't be spoofed. State is stored on the quote
    ('gst', 'kyc') so later GET/PATCH calls keep the verified status."""
    if quote_id not in _STORE:
        raise HTTPException(404, "quote not found")
    res = kyc.get_session(body.kyc_session_id)["result"]
    if res is None:
        raise HTTPException(409, "KYC not validated yet")
    return apply_kyc_result(quote_id, res)
