"""Pure, dependency-light validation primitives. No I/O, so they are trivial to unit test."""
from __future__ import annotations

import itertools
import re
from datetime import date, datetime

from rapidfuzz import fuzz

from ..config import MAX_GSTIN_OCR_EDITS, NAME_MATCH_MIN, ADDRESS_MATCH_MIN

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# 2 digits | 5 letters | 4 digits | 1 letter | entity no. | 'Z' | check char.
# The README says the PAN's 4th char is always 'X' in this dataset, so we do NOT restrict it to real entity types.
GSTIN_RE = re.compile(r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]")
UDYAM_RE = re.compile(r"UDYAM-[A-Z]{2}-\d{2}-\d{7}")

# Glyphs Tesseract confuses on these documents (seen: I->T, O<->0).
_CONFUSABLE = {"0": "O", "O": "0", "1": "I", "I": "1TJ", "T": "I", "J": "I", "5": "S", "S": "5", "8": "B", "B": "8", "2": "Z", "Z": "2"}


# ---------- GSTIN ----------
def gstin_check_char(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    return _CHARS[(36 - total % 36) % 36]


def gstin_checksum_ok(g: str) -> bool:
    return bool(GSTIN_RE.fullmatch(g)) and gstin_check_char(g[:14]) == g[14]


def clean_gstin(raw: str | None) -> str | None:
    if not raw:
        return None
    return re.sub(r"[^A-Za-z0-9]", "", raw).upper() or None


# def correct_gstin_ocr(raw: str | None, *, exists=lambda g: False) -> tuple[str | None, bool]:
#     """Return (best_gstin, was_corrected).

#     Tries the raw string, then up to MAX_GSTIN_OCR_EDITS confusable-glyph substitutions, and only
#     ever returns a candidate that passes the checksum. If several pass, one present in the registry wins.
#     We never 'snap' to the registry by fuzzy distance: that would silently repair a tampered number.
#     """
#     s = clean_gstin(raw)
#     if not s:
#         return s, False
#     if len(s) == 16:  # OCR sometimes splits one glyph into two ('I' -> 'IT'); try dropping one char
#         drops = [s[:i] + s[i + 1:] for i in range(16) if gstin_checksum_ok(s[:i] + s[i + 1:])]
#         if drops:
#             drops.sort(key=lambda c: not exists(c))
#             return drops[0], True
#         return s, False
#     if len(s) != 15:
#         return s, False
#     if gstin_checksum_ok(s):
#         return s, False
#     slots = [i for i, c in enumerate(s) if c in _CONFUSABLE]
#     found: list[str] = []
#     for n in range(1, MAX_GSTIN_OCR_EDITS + 1):
#         for idxs in itertools.combinations(slots, n):
#             for repl in itertools.product(*[_CONFUSABLE[s[i]] for i in idxs]):
#                 cand = list(s)
#                 for i, r in zip(idxs, repl):
#                     cand[i] = r
#                 c = "".join(cand)
#                 if gstin_checksum_ok(c):
#                     found.append(c)
#         if found:
#             break  # prefer the fewest edits
#     if not found:
#         return s, False
#     found.sort(key=lambda c: not exists(c))
#     return found[0], True


def correct_gstin_ocr(raw: str | None, *, exists=lambda g: False) -> tuple[str | None, bool]:
    """Correct OCR confusions and one extra character in a GSTIN.

    Only return candidates that pass the GSTIN checksum.
    Prefer candidates present in the registry.
    Never use fuzzy registry matching.
    """
    s = clean_gstin(raw)
    if not s:  # nothing usable was read (clean_gstin returns None)
        return s, False

    # If the original GSTIN is already valid, no correction is needed.
    if len(s) == 15 and gstin_checksum_ok(s):
        return s, False

    # OCR may insert one extra character.
    if len(s) == 16:
        bases = [s[:i] + s[i + 1:] for i in range(len(s))]
    elif len(s) == 15:
        bases = [s]
    else:
        return s, False

    # First check candidates requiring deletion only.
    found = set()

    for base in bases:
        if gstin_checksum_ok(base):
            found.add(base)

    if found:
        result = sorted(found, key=lambda c: not exists(c))[0]
        return result, True

    # Then try confusable-character corrections.
    for n in range(1, MAX_GSTIN_OCR_EDITS + 1):
        found = set()

        for base in bases:
            slots = [
                i for i, ch in enumerate(base)
                if ch in _CONFUSABLE
            ]

            for idxs in itertools.combinations(slots, n):
                choices = [_CONFUSABLE[base[i]] for i in idxs]

                for replacements in itertools.product(*choices):
                    candidate = list(base)

                    for i, replacement in zip(idxs, replacements):
                        candidate[i] = replacement

                    candidate = "".join(candidate)

                    if gstin_checksum_ok(candidate):
                        found.add(candidate)

        if found:
            result = sorted(found, key=lambda c: not exists(c))[0]
            return result, True

    return s, False



def mask_gstin(g: str | None) -> str:
    return "—" if not g else g[:2] + "•" * 9 + g[-4:]


# ---------- Udyam ----------
def clean_udyam(raw: str | None) -> str | None:
    if not raw:
        return None
    s = re.sub(r"\s+", "", raw).upper().replace("—", "-")
    return s


# ---------- names & addresses ----------
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def proprietor_and_trade(legal_name: str | None) -> tuple[str | None, str | None]:
    """'Neha Banerjee (Prop. Neelgiri Physio Clinic)' -> ('Neha Banerjee', 'Neelgiri Physio Clinic')."""
    if not legal_name:
        return None, None
    m = re.match(r"(.+?)\s*\(\s*Prop\.?\s*(.+?)\s*\)\s*$", legal_name.strip(), re.I)
    return (m.group(1), m.group(2)) if m else (None, legal_name.strip())


def names_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return fuzz.token_sort_ratio(_norm(a), _norm(b)) >= NAME_MATCH_MIN or _norm(a) == _norm(b)


def legal_names_match(a: str | None, b: str | None) -> bool:
    """Compare 'Person (Prop. Trade Name)' strings part by part. A whole-string fuzzy score hides a one-word
    difference inside a long string (e.g. 'Shri' vs 'Neelgiri' still scores 88), so each part must match on its own."""
    if not a or not b:
        return False
    pa, ta = proprietor_and_trade(a)
    pb, tb = proprietor_and_trade(b)
    if (pa is None) != (pb is None):  # one side is a proprietorship string, the other isn't
        return False
    return (pa is None or names_match(pa, pb)) and names_match(ta, tb)


def addresses_match(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return fuzz.ratio(_norm(a), _norm(b)) >= ADDRESS_MATCH_MIN


def pincode(addr: str | None) -> str | None:
    found = re.findall(r"\d{6}", addr or "")
    return found[-1] if found else None


# ---------- dates ----------
def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip().replace(".", "-")
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None
