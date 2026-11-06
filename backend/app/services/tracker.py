"""Order state machine, expected dates and the customer-facing timeline."""
from __future__ import annotations

from datetime import date, timedelta

from . import data

# status codes in order
STEPS = [
    ("QUOTE_ACCEPTED", "Quote accepted"),
    ("KYC_VERIFIED", "Documents verified"),
    ("ESIGNED", "Agreement signed"),
    ("PAYMENT_RECEIVED", "Payment received"),
    ("INSTALL_SCHEDULED", "Installation scheduled"),
    ("INSTALLED", "Installed"),
    ("ACTIVATED", "Services active"),
]
CODES = [c for c, _ in STEPS]
LABEL = dict(STEPS)

NEXT_ACTION = {
    "KYC_VERIFIED": "Sign your agreement",
    "ESIGNED": "Pay to start installation",
    "PAYMENT_RECEIVED": "Nothing needed from you. We're scheduling installation",
    "INSTALL_SCHEDULED": "Nothing needed from you. Keep the premises accessible on the install day",
    "INSTALLED": "Nothing needed from you. Services go live tomorrow",
    "ACTIVATED": "All done",
}


def install_days(order: dict) -> int:
    cat = data.catalogue()
    return max((cat[i["product_id"]].install_days for i in order["items"]), default=1)


def expected_dates(order: dict) -> dict[str, date]:
    """Expected date per step. Re-based on the dates steps *actually* happened, so a failed payment
    pushes the install date out honestly instead of leaving a stale promise."""
    done = order["done"]                               # code -> date
    exp: dict[str, date] = {}
    d0 = done["QUOTE_ACCEPTED"]
    exp["QUOTE_ACCEPTED"] = d0
    exp["KYC_VERIFIED"] = done.get("KYC_VERIFIED", d0)
    cur = exp["KYC_VERIFIED"]
    gaps = {"ESIGNED": 1, "PAYMENT_RECEIVED": 0, "INSTALL_SCHEDULED": 0,
            "INSTALLED": install_days(order), "ACTIVATED": 1}
    for code in CODES[2:]:
        if code in done:
            cur = done[code]
        else:
            cur = max(cur + timedelta(days=gaps[code]), order["clock"])   # never promise a date in the past
        exp[code] = cur
    return exp


def timeline(order: dict) -> dict:
    exp = expected_dates(order)
    done = order["done"]
    status = order["status"]
    steps = []
    current_found = False
    for code, label in STEPS:
        if code in done:
            state = "done"
        elif not current_found:
            state = "failed" if (code == "PAYMENT_RECEIVED" and order["payment"]["last_result"] == "failed") else "current"
            current_found = True
        else:
            state = "upcoming"
        steps.append(dict(code=code, label=label, state=state,
                          done_on=str(done[code]) if code in done else None,
                          expected_on=str(exp[code])))
    p_day = done.get("PAYMENT_RECEIVED") or exp["PAYMENT_RECEIVED"]
    cat = data.catalogue()
    items = [dict(product_id=i["product_id"], name=i["product_name"], qty=i["qty"],
                  expected_live_on=str(p_day + timedelta(days=cat[i["product_id"]].install_days)))
             for i in order["items"]]
    return dict(order_id=order["order_id"], status=status, as_of=str(order["clock"]),
                next_action=NEXT_ACTION.get(status, ""), expected_activation=str(exp["ACTIVATED"]),
                days_to_activation=max(0, (exp["ACTIVATED"] - order["clock"]).days),
                steps=steps, items=items, notifications=order["notifications"])
