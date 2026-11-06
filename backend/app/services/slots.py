"""Advisor slot schema, validation, offline extraction and the (templated) follow-up questions.

Everything the LLM returns passes through `sanitize`, so a confused or manipulated model can only set
well-formed values for known slots."""
from __future__ import annotations

import re

from pydantic import BaseModel

from . import data
from .recommender import NEED_MAP, needs_to_products
from .validators import GSTIN_RE, clean_gstin, gstin_checksum_ok

REQUIRED = ["business_type", "employees", "sites", "city", "has_gstin"]
INTERNET = ["Business broadband", "Home broadband", "Mobile hotspot", "Leased line", "Mixed per site"]
CITY_ALIASES = {"bangalore": "Bengaluru", "calcutta": "Kolkata", "madras": "Chennai", "mysore": "Mysuru",
                "vizag": "Visakhapatnam", "baroda": "Vadodara", "cochin": "Kochi", "bombay": "Mumbai"}


class Slots(BaseModel):
    business_type: str | None = None
    employees: int | None = None
    sites: int | None = None
    city: str | None = None
    has_gstin: bool | None = None
    gstin: str | None = None
    current_internet: str | None = None
    needs: list[str] = []
    budget_monthly: int | None = None
    asked_needs: bool = False


def missing(s: Slots) -> list[str]:
    return [k for k in REQUIRED if getattr(s, k) is None]


def next_slot(s: Slots) -> str | None:
    m = missing(s)
    if m:
        return m[0]
    return None if s.asked_needs else "needs"


def tier_for(city: str | None) -> tuple[int, bool]:
    """(tier, known). Unknown cities get tier 2 (the safer, narrower catalogue) rather than a guess upward."""
    if city:
        t = data.city_tiers().get(city)
        if t:
            return t, True
    return 2, False


# ---------- validation of anything that came from a model or a regex ----------
def _int(v, lo, hi):
    try:
        n = int(float(str(v).replace(",", "").strip()))
    except (ValueError, TypeError):
        return None
    return n if lo <= n <= hi else None


def _canon_city(v) -> str | None:
    if not isinstance(v, str):
        return None
    c = re.sub(r"[^A-Za-z .-]", "", v).strip()[:40]
    if not c:
        return None
    low = c.lower()
    if low in CITY_ALIASES:
        return CITY_ALIASES[low]
    for k in data.city_tiers():
        if k.lower() == low:
            return k
    return c.title()


def sanitize(raw: dict) -> dict:
    out: dict = {}
    if isinstance(raw.get("business_type"), str):
        b = re.sub(r"[^A-Za-z &/-]", "", raw["business_type"]).strip()[:60]
        if len(b) >= 3:
            out["business_type"] = b
    if (n := _int(raw.get("employees"), 1, 500)) is not None:
        out["employees"] = n
    if (n := _int(raw.get("sites"), 1, 100)) is not None:
        out["sites"] = n
    if (c := _canon_city(raw.get("city"))):
        out["city"] = c
    if isinstance(raw.get("has_gstin"), bool):
        out["has_gstin"] = raw["has_gstin"]
    if (n := _int(raw.get("budget_monthly"), 500, 1_000_000)) is not None:
        out["budget_monthly"] = n
    ci = raw.get("current_internet")
    if isinstance(ci, str) and ci in INTERNET:
        out["current_internet"] = ci
    if isinstance(raw.get("needs"), list):
        needs = [str(x)[:20] for x in raw["needs"][:8] if isinstance(x, (str, int))]
        pids = needs_to_products(needs)
        if pids:
            out["needs"] = pids
    return out


# ---------- GSTIN typed by the user: validated locally, never by the model ----------
def find_gstin(message: str) -> tuple[str | None, bool]:
    """(valid_gstin, looked_like_one_but_invalid)"""
    bad = False
    for tok in re.findall(r"\b[A-Za-z0-9]{15}\b", message.upper()):
        if GSTIN_RE.fullmatch(tok):
            if gstin_checksum_ok(tok):
                return tok, False
            bad = True
    return None, bad


# ---------- offline extractor (also the fallback when the LLM is down) ----------
_YES = {"yes", "y", "haan", "han", "ha", "हाँ", "हां", "हा", "जी", "है", "hai"}
_NO = {"no", "n", "nahi", "nahin", "nope", "नहीं", "नही", "nahi hai"}


def extract_offline(message: str, expecting: str | None) -> dict:
    m = message.strip()
    low = m.lower()
    out: dict = {}
    if (x := re.search(r"(\d+)\s*(?:employees?|staff|people|workers|members|persons|karmchari|कर्मचारी)", low)) or \
       (x := re.search(r"team of (\d+)", low)):
        out["employees"] = x.group(1)
    if (x := re.search(r"(\d+)\s*(?:shops?|stores?|outlets?|branch(?:es)?|locations?|sites?|offices?|centres?|"
                       r"showrooms?|restaurants?|clinics?|gyms?|hotels?)", low)):
        out["sites"] = x.group(1)
    for alias, canon in list(CITY_ALIASES.items()) + [(c.lower(), c) for c in data.city_tiers()]:
        if re.search(rf"\b{re.escape(alias)}\b", low):
            out["city"] = canon
            break
    for bt in data.business_types():
        if bt.lower() in low:
            out["business_type"] = bt
            break
    if re.search(r"(?:\b(?:no|dont|don't|without|nahi|nahin)\b.{0,12}\bgst)|(?:\bgst\w*\b.{0,12}\b(?:nahi|nahin|no)\b)", low):
        out["has_gstin"] = False
    elif re.search(r"\b(?:have|got|with|hai)\b.{0,10}\bgst", low) or re.search(r"\bgst\w*\b.{0,10}\b(?:yes|hai|haan)\b", low):
        out["has_gstin"] = True
    if (x := re.search(r"(?:budget|₹|rs\.?|inr)\s*(?:of|is|around|about|upto|up to)?\s*(\d[\d,]*)\s*(k)?", low)):
        n = int(x.group(1).replace(",", "") or 0)
        out["budget_monthly"] = n * 1000 if x.group(2) else n
    for name in INTERNET:
        if name.lower() in low:
            out["current_internet"] = name
    if "hotspot" in low:
        out["current_internet"] = "Mobile hotspot"
    found = [pid for kw, pid in NEED_MAP.items() if kw in low]
    if found:
        out["needs"] = list(dict.fromkeys(found))
    # a bare answer to the question we just asked
    tok = low.strip(" .!?")
    if expecting in ("employees", "sites") and re.fullmatch(r"\d+", tok):
        out.setdefault(expecting, tok)
    elif expecting == "has_gstin" and "has_gstin" not in out:
        if tok in _YES:
            out["has_gstin"] = True
        elif tok in _NO:
            out["has_gstin"] = False
    elif expecting == "city" and "city" not in out and re.fullmatch(r"[a-z .-]{3,40}", tok) and tok not in _YES | _NO:
        out["city"] = tok
    elif expecting == "business_type" and "business_type" not in out and re.fullmatch(r"[A-Za-z &/-]{3,60}", m):
        out["business_type"] = m
    return out


# ---------- questions (templated so the demo never depends on the model) ----------
Q = {
    "business_type": {"en": "What kind of business do you run? For example, a kirana store, clinic, factory or restaurant chain.",
                      "hi": "आप किस तरह का बिज़नेस चलाते हैं? जैसे किराना दुकान, क्लिनिक, फैक्ट्री या रेस्टोरेंट चेन।"},
    "employees": {"en": "How many people work in your business, including you?",
                  "hi": "आपके बिज़नेस में आप समेत कुल कितने लोग काम करते हैं?"},
    "sites": {"en": "How many locations (shops, branches or offices) do you have?",
              "hi": "आपकी कितनी जगह (दुकानें, ब्रांच या ऑफिस) हैं?"},
    "city": {"en": "Which city is your business in?", "hi": "आपका बिज़नेस किस शहर में है?"},
    "has_gstin": {"en": "Do you have a GST registration (GSTIN)? You can just say yes or no. You can type the number too.",
                  "hi": "क्या आपके पास GST रजिस्ट्रेशन (GSTIN) है? बस हाँ या नहीं बताइए। चाहें तो नंबर भी लिख सकते हैं।"},
    "needs": {"en": "Anything specific you need, like billing/POS, CCTV, Wi-Fi, business email or phone lines? Say 'no' to see my recommendation.",
              "hi": "कुछ खास चाहिए, जैसे बिलिंग/POS, CCTV, Wi-Fi, बिज़नेस ईमेल या फ़ोन लाइन? सीधे सुझाव देखने के लिए 'नहीं' कहें।"},
}


def question(slot: str, lang: str) -> str:
    return Q[slot].get(lang, Q[slot]["en"])
