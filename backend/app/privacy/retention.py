"""Deletes data when its retention period ends. Runs on a timer (see main.py) and can be called directly."""
from __future__ import annotations

import time

from . import audit, policy


def purge_all(now: float | None = None) -> dict[str, int]:
    from ..routers import kyc, orders, quote
    from ..services import advisor
    now = time.time() if now is None else now
    counts = {"kyc_sessions": 0, "advisor_sessions": 0, "quotes": 0, "orders": 0, "orphaned_upload_folders": 0}

    for sid in [k for k, v in kyc._SESSIONS.items() if v["expires"] < now]:
        kyc._purge(sid)
        counts["kyc_sessions"] += 1
    counts["orphaned_upload_folders"] = kyc.sweep_orphans()
    for sid in [k for k, v in advisor._SESSIONS.items() if now - v.created > policy.ADVISOR_HOURS * 3600]:
        del advisor._SESSIONS[sid]
        counts["advisor_sessions"] += 1
    for qid in [k for k, v in quote._STORE.items() if now - v.get("created", now) > policy.QUOTE_HOURS * 3600]:
        del quote._STORE[qid]
        counts["quotes"] += 1
    for oid in [k for k, v in orders._ORDERS.items() if now - v.get("created", now) > policy.ORDER_DAYS * 86400]:
        del orders._ORDERS[oid]
        counts["orders"] += 1
    if any(counts.values()):
        audit.log("retention_purge", **counts)
    return counts
