"""Segment templates, quantity rules and the assembly of a quote."""
from __future__ import annotations

import math
import uuid

from ..config import DEFAULT_PRICE_POSITION
from ..schemas import Blocked, Profile, Quote, QuoteLine
from . import data, eligibility as el
from .pricing import line_totals
from .segmenter import MICRO, MFG, MULTI, PROF

# Core = included by default. Optional = offered as toggles (off) unless the
# owner asked for them. Order of optional = popularity in activated bundles.
TEMPLATES = {
    MICRO: dict(core=["conn", "P07"], optional=["P19", "P22", "P23", "P15", "P18"]),
    PROF: dict(core=["conn", "P16", "P08"], optional=["P20", "P07", "P17", "P12", "P11"]),
    MFG: dict(core=["conn", "P08", "P16"], optional=["P20", "P21", "P11", "P23", "P24"]),
    MULTI: dict(core=["conn", "P08", "P09"], optional=["P19", "P23", "P10", "P22", "P13", "P15"]),
}
CONN_PREF = {
    MICRO: ["P01", "P04"],
    PROF: ["P02", "P01", "P04"],   # P02 only picked for 10+ staff, see _conn_order
    MFG: ["P05", "P02", "P01"],
    MULTI: ["P02", "P01"],
}
PER_SITE = {"P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10", "P21", "P22"}

# Plain-language keyword -> product
NEED_MAP = {
    "pos": "P19", "billing": "P19", "counter": "P19",
    "wifi": "P22", "wi-fi": "P22", "guest": "P22",
    "cctv": "P23", "camera": "P23",
    "email": "P16", "office": "P16",
    "website": "P18", "domain": "P18",
    "whatsapp": "P15", "sms": "P14",
    "backup": "P17", "security": "P20", "antivirus": "P20", "firewall": "P21",
    "phone": "P12", "sip": "P12", "ivr": "P12", "tollfree": "P13",
    "failover": "P09", "sdwan": "P10", "sd-wan": "P10",
    "static ip": "P11", "iot": "P24", "tracker": "P25", "tracking": "P25",
    "mobile": "P08", "sim": "P08", "leased line": "P05",
}


def needs_to_products(needs: list[str]) -> list[str]:
    out: list[str] = []
    cat = data.catalogue()
    for n in needs:
        n = n.strip()
        pid = n.upper() if n.upper() in cat else None
        if not pid:
            low = n.lower()
            pid = next((v for k, v in NEED_MAP.items() if k in low), None)
        if pid and pid not in out:
            out.append(pid)
    return out


def default_qty(pid: str, p: Profile, seg: str) -> int:
    e, s = p.employees, p.sites
    clamp = lambda x, lo, hi: max(lo, min(hi, x))
    if pid in PER_SITE:
        return s
    if pid == "P07":
        return clamp(e, 1, 2) if seg == MICRO else clamp(round(0.1 * e), 1, 4)
    if pid == "P08":
        k = {PROF: 0.2, MFG: 0.06, MULTI: 0.065}.get(seg, 0.2)
        return clamp(round(k * e), 1, 6)
    if pid == "P16":
        k = {PROF: 0.55, MFG: 0.15, MULTI: 0.15, MICRO: 0.5}[seg]
        return clamp(round(k * e), 1, e)
    if pid == "P20":
        k = {PROF: 0.45, MFG: 0.12, MULTI: 0.1, MICRO: 0.5}[seg]
        return clamp(round(k * e), 1, e)
    if pid == "P12":
        return clamp(math.ceil(e / 6), 3, 4)
    if pid == "P19":
        return s if seg == MULTI else 1
    if pid == "P23":
        return {MICRO: 1, MFG: 5, MULTI: round(1.5 * s)}.get(seg, 2)
    if pid == "P24":
        return clamp(round(0.12 * e), 1, 12)
    return 1


def _conn_order(seg: str, p: Profile) -> list[str]:
    order = list(CONN_PREF[seg])
    if seg == PROF and p.employees < 10:
        order = ["P01", "P02", "P04"]
    return order


def _compose(p: Profile, seg: str, gst_ok: bool, gst_msg: str, selections: dict | None):
    """Returns (selections, blocked, notes). selections: pid -> dict(included, qty, role, reason)."""
    cat = data.catalogue()
    notes: list[str] = []
    blocked: dict[str, Blocked] = {}

    def fails(pid):
        return el.rule_failures(cat[pid], p, gst_ok, gst_msg)

    def block(pid, reasons):
        alt = next((a for a in el.ALTERNATIVES.get(pid, []) if not fails(a)), None)
        up = ""
        if any("GSTIN" in r for r in reasons):
            up = "Add an active GSTIN to unlock this later."
        blocked[pid] = Blocked(product_id=pid, product_name=cat[pid].product_name,
                               reasons=reasons, alternative=alt, upgrade_path=up)

    if selections is None:
        selections = {}
        tpl = TEMPLATES[seg]
        wanted = needs_to_products(p.needs)
        # connectivity
        conn = None
        for c in _conn_order(seg, p):
            f = fails(c)
            if f:
                if c in el.ALTERNATIVES or cat[c].requires_gstin or c == "P05":
                    block(c, f)
                continue
            conn = c
            break
        if conn is None:
            conn = "P01" if not fails("P01") else "P04"
        for pid in tpl["core"]:
            if pid == "conn":
                pid = conn
            f = fails(pid)
            if f:
                block(pid, f)
                continue
            selections[pid] = dict(included=True, qty=default_qty(pid, p, seg), role="core",
                                   reason="Recommended for " + seg.lower())
        for pid in wanted:
            if pid in selections:
                continue
            f = fails(pid)
            if f:
                block(pid, f)
                continue
            selections[pid] = dict(included=True, qty=default_qty(pid, p, seg), role="need",
                                   reason="You asked for this")
        for pid in tpl["optional"]:
            if pid in selections or pid in blocked:
                continue
            f = fails(pid)
            if f:
                if cat[pid].requires_gstin:  # worth surfacing as an upgrade path
                    block(pid, f)
                continue
            selections[pid] = dict(included=False, qty=default_qty(pid, p, seg), role="addon",
                                   reason="Popular with similar businesses")
        # a requested need that was blocked can still have an eligible alternative: leave as upgrade path only
    else:
        # a user-edited selection: re-check static rules on everything included
        for pid in list(selections):
            f = fails(pid)
            if f and selections[pid]["included"]:
                block(pid, f)
                del selections[pid]
                notes.append(f"{cat[pid].product_name} can't be added: {f[0]}.")
    # dependencies (auto-add or block / cascade)
    changed = True
    while changed:
        changed = False
        inc = {k for k, v in selections.items() if v["included"]}
        for pid, v in list(selections.items()):
            prod = cat[pid]
            if not v["included"] or el.dependency_met(prod, inc):
                continue
            has_conn = any(cat[i].is_connectivity for i in inc)
            cand = next((d for d in prod.requires_one_of if not fails(d)), None)
            if cand and not has_conn:
                selections[cand] = dict(included=True, qty=default_qty(cand, p, seg), role="dependency",
                                        reason=f"Needed for {prod.product_name}")
                notes.append(f"Added {cat[cand].product_name} because {prod.product_name} needs a connection.")
            else:
                names = " / ".join(cat[d].product_name for d in prod.requires_one_of[:3])
                v["included"] = False
                block(pid, [f"needs one of: {names} in the same bundle"])
                del selections[pid]
                notes.append(f"{prod.product_name} was left out: it needs a compatible connection.")
            changed = True
            break
    return selections, list(blocked.values()), notes


def assemble(p: Profile, selections: dict | None = None, quote_id: str | None = None,
             position: float | None = None, gst_status: str | None = None,
             kyc_decision: str | None = None) -> tuple[Quote, dict]:
    cat = data.catalogue()
    seg = classify_seg(p)
    status = gst_status or data.gstin_status(p.gstin)
    gst_ok, gst_msg = el.gstin_ok(status, p)
    sel, blocked, notes = _compose(p, seg, gst_ok, gst_msg, selections)
    pos = DEFAULT_PRICE_POSITION if position is None else position
    if status in ("Cancelled", "Suspended", "Unknown"):
        notes.append(f"GSTIN check: {gst_msg}. A GSTIN-free starter bundle is shown.")
    elif status == "None" and not p.has_gstin:
        notes.append("No GSTIN: showing a starter bundle. Adding a GSTIN unlocks more products.")

    def total(position):
        m = s = 0
        for pid, v in sel.items():
            if v["included"]:
                _, lm, ls = line_totals(cat[pid], v["qty"], position)
                m += lm; s += ls
        return m, s

    within = None
    if p.budget_monthly:
        m, _ = total(pos)
        if m > p.budget_monthly:
            pos = 0.0
            m, _ = total(pos)
            notes.append("Priced at the lowest catalogue rates to fit your budget.")
        # drop need/dependency-free extras (never core) until it fits
        if m > p.budget_monthly:
            for pid in [k for k, v in sel.items() if v["included"] and v["role"] == "need"][::-1]:
                sel[pid]["included"] = False
                notes.append(f"{cat[pid].product_name} moved to optional to stay in budget.")
                if total(pos)[0] <= p.budget_monthly:
                    break
        within = total(pos)[0] <= p.budget_monthly
    if kyc_decision and kyc_decision not in ("PASS", "RESTRICTED"):
        notes.append("Identity check still open: GST-based products are confirmed once KYC passes.")

    lines = []
    for pid, v in sel.items():
        up, lm, ls = line_totals(cat[pid], v["qty"], pos)
        lines.append(QuoteLine(product_id=pid, product_name=cat[pid].product_name, unit=cat[pid].unit,
                               qty=v["qty"], unit_price=up, line_monthly=lm, line_setup=ls,
                               included=v["included"], role=v["role"], reason=v["reason"]))
    order = {"core": 0, "dependency": 1, "need": 2, "addon": 3}
    lines.sort(key=lambda l: (order[l.role], l.product_id))
    inc = [l for l in lines if l.included]
    m, s = total(pos)
    q = Quote(
        quote_id=quote_id or uuid.uuid4().hex[:10], segment=seg, profile=p, gstin_status=status, lines=lines,
        monthly_total=m, setup_total=s,
        contract_months=max([cat[l.product_id].min_contract_months for l in inc], default=0),
        expected_install_days=max([cat[l.product_id].install_days for l in inc], default=0),
        price_position=pos, within_budget=within, blocked=blocked, notes=notes, kyc_decision=kyc_decision,
    )
    return q, sel


def classify_seg(p: Profile) -> str:
    from .segmenter import classify
    return classify(p)
