"""Where each signed-in person has got to. One row per account, written by the routers as they act, so
the server (not the browser) is the record of progress."""
from __future__ import annotations

import json
import time
from datetime import date

from .. import db

RANK = {"registered": 0, "advisor": 1, "quote": 2, "kyc": 3, "sign": 4, "track": 5}
_JSON = {"slots", "selections"}


def ensure(user_id: int) -> dict:
    now = time.time()
    with db.connect() as c:
        c.execute("INSERT OR IGNORE INTO journeys(user_id,created,updated) VALUES(?,?,?)", (user_id, now, now))
    return get(user_id)


def get(user_id: int) -> dict | None:
    with db.connect() as c:
        r = c.execute("SELECT * FROM journeys WHERE user_id=?", (user_id,)).fetchone()
    if not r:
        return None
    j = dict(r)
    for k in _JSON:
        j[k] = json.loads(j[k] or "{}")
    return j


def update(user_id: int, stage: str | None = None, **fields) -> None:
    """Stage only moves forward. Everything else overwrites."""
    cur = ensure(user_id)
    if stage and RANK[stage] > RANK.get(cur["stage"], 0):
        fields["stage"] = stage
    fields["updated"] = time.time()
    cols, vals = [], []
    for k, v in fields.items():
        cols.append(f"{k}=?")
        vals.append(json.dumps(v) if k in _JSON else v)
    with db.connect() as c:
        c.execute(f"UPDATE journeys SET {', '.join(cols)} WHERE user_id=?", (*vals, user_id))


def from_quote(user_id: int, q, selections: dict, position: float, stage: str = "quote") -> None:
    update(user_id, stage, quote_id=q.quote_id, selections=selections, price_position=position, segment=q.segment,
           monthly_total=q.monthly_total, setup_total=q.setup_total, blocked_count=len(q.blocked),
           within_budget=None if q.within_budget is None else int(q.within_budget), gst_status=q.gstin_status
           if q.gstin_status in ("Cancelled", "Suspended", "Active") else None)


def reset(user_id: int) -> None:
    """Start over: keeps the account, drops the saved progress."""
    with db.connect() as c:
        c.execute("DELETE FROM journeys WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    ensure(user_id)


# ---------- orders ----------
def _enc(o: dict) -> str:
    def d(x):
        if isinstance(x, date):
            return {"__date__": x.isoformat()}
        raise TypeError(type(x))
    return json.dumps(o, default=d)


def _dec(s: str) -> dict:
    return json.loads(s, object_hook=lambda d: date.fromisoformat(d["__date__"]) if "__date__" in d else d)


def save_order(user_id: int, o: dict) -> None:
    with db.connect() as c:
        c.execute("INSERT INTO orders(order_id,user_id,data,updated) VALUES(?,?,?,?) "
                  "ON CONFLICT(order_id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
                  (o["order_id"], user_id, _enc(o), time.time()))


def load_order(order_id: str) -> tuple[dict, int] | None:
    with db.connect() as c:
        r = c.execute("SELECT user_id,data FROM orders WHERE order_id=?", (order_id,)).fetchone()
    return (_dec(r["data"]), r["user_id"]) if r else None
