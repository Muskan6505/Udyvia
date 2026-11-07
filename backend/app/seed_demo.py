"""Fills the database with sample unfinished leads for the back-office demo.

Each one is taken from a real row of data/smb_leads.csv that dropped out at the needs / quote / KYC stage, then
run through the real rules engine, so the quote values and blockers are what the product would really show.
Names and phone numbers are made up (the numbers are not real) and every account is flagged as demo.

    python -m app.seed_demo            # adds 14 sample leads
    python -m app.seed_demo --clear    # removes them again
"""
from __future__ import annotations

import csv
import random
import sys
import time

from . import auth, db
from .config import DATA_DIR
from .schemas import Profile
from .services import journey, slots as sl
from .services.recommender import assemble

STAGE_MAP = {"Needs assessed": "quote", "Quote accepted": "kyc", "KYC complete": "kyc"}


def seed(count: int = 14, seed_value: int = 11) -> int:
    db.init()
    rng = random.Random(seed_value)
    with open(DATA_DIR / "smb_leads.csv", newline="", encoding="utf-8") as f:
        pool = [r for r in csv.DictReader(f) if r["outcome"] == "Dropped" and r["stage_reached"] in STAGE_MAP and r["current_internet"]]
    rng.shuffle(pool)
    made = 0
    pw = auth.hash_password(__import__("secrets").token_urlsafe(16))        # nobody can sign in to a demo account
    for r in pool:
        if made >= count:
            break
        city = r["city"]
        tier, _ = sl.tier_for(city)
        email = f"{r['lead_id'].lower()}@demo.udyvia.example"
        now = time.time()
        with db.connect() as c:
            if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                continue
            cur = c.execute("INSERT INTO users(email,name,phone,pw_hash,contact_consent,consent_at,is_demo,created) VALUES(?,?,?,?,?,?,1,?)",
                            (email, r["contact_name"], f"90000{rng.randint(10000, 99999)}", pw, 1, now, now))
            uid = cur.lastrowid
        has_g = r["has_gstin"] == "Y"
        slots = sl.Slots(business_type=r["business_type"], employees=int(r["employee_count"]), sites=int(r["num_sites"]), city=city,
                         has_gstin=has_g, current_internet=r["current_internet"], asked_needs=True).model_dump()
        prof = Profile(business_type=r["business_type"], employees=int(r["employee_count"]), sites=int(r["num_sites"]), city=city,
                       city_tier=tier, has_gstin=has_g, current_internet=r["current_internet"])
        q, sel = assemble(prof)
        stage = STAGE_MAP[r["stage_reached"]]
        journey.ensure(uid)
        journey.update(uid, "advisor", slots=slots, lang="en")
        journey.from_quote(uid, q, sel, q.price_position, stage="quote")
        fields = {}
        if r["stage_reached"] == "KYC complete":
            fields["kyc_decision"] = rng.choice(["PASS", "RESTRICTED", "MANUAL_REVIEW"] if not has_g else ["PASS", "MANUAL_REVIEW", "NEEDS_FIX"])
        elif r["stage_reached"] == "Quote accepted":
            fields["kyc_decision"] = rng.choice([None, "NEEDS_FIX"])
        journey.update(uid, stage, kyc_session_id=None, **fields)
        # spread "last activity" over the last 3 days so the idle column varies
        with db.connect() as c:
            c.execute("UPDATE journeys SET updated=? WHERE user_id=?", (now - rng.randint(20, 72 * 60) * 60, uid))
        made += 1
    return made


def clear() -> int:
    with db.connect() as c:
        return c.execute("DELETE FROM users WHERE is_demo=1").rowcount


if __name__ == "__main__":
    if "--clear" in sys.argv:
        print("removed", clear(), "demo leads")
    else:
        print("added", seed(), "demo leads")
