"""Deterministic segment classification (no LLM)."""
from __future__ import annotations

from ..schemas import Profile

MICRO, PROF, MFG, MULTI = (
    "Micro retail & services",
    "Professional offices",
    "Small manufacturers",
    "Small multi-site businesses",
)
SHORT = {MICRO: "micro", PROF: "prof", MFG: "mfg", MULTI: "multi"}

_MFG_WORDS = ("unit", "workshop", "press", "factory", "mill", "manufactur", "plant")
_PROF_WORDS = ("clinic", "lab", "firm", "office", "studio", "agency", "centre", "coaching", "advocate", "consult")
_MICRO_WORDS = ("shop", "store", "bakery", "boutique", "salon", "pharmacy", "optician", "kirana", "repair")


def classify(p: Profile) -> str:
    if p.segment in SHORT:
        return p.segment
    if p.sites >= 3:
        return MULTI
    t = p.business_type.lower()
    if any(w in t for w in _MFG_WORDS):
        return MFG
    if any(w in t for w in _PROF_WORDS):
        return PROF
    if any(w in t for w in _MICRO_WORDS):
        return MICRO
    # fall back on size
    if p.employees >= 40:
        return MFG
    return MICRO if p.employees <= 6 else PROF
