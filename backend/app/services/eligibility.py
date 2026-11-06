"""Catalogue rules: tier, size, GSTIN, dependencies. Pure functions."""
from __future__ import annotations

from ..schemas import Product, Profile

# Offered instead when a GSTIN-gated (or size-gated) product is blocked.
ALTERNATIVES = {"P03": ["P02"], "P05": ["P02", "P01"], "P06": ["P05", "P02"]}


def gstin_ok(status: str, p: Profile) -> tuple[bool, str]:
    """Is there a valid, active GSTIN? Returns (ok, explanation)."""
    if status == "Active":
        return True, ""
    if status == "None":
        if p.has_gstin:
            return True, ""            # claimed, number not given yet: verify at KYC
        return False, "needs an active GSTIN"
    if status == "Unknown":
        return False, "GSTIN not found in the registry"
    return False, f"GSTIN is {status.lower()}"


def rule_failures(prod: Product, p: Profile, gst_ok: bool, gst_msg: str) -> list[str]:
    """Static rules only (not dependencies)."""
    out = []
    if p.city_tier not in prod.city_tiers:
        out.append(f"not sold in tier {p.city_tier} cities")
    if p.employees < prod.min_employees:
        out.append(f"needs at least {prod.min_employees} employees")
    if p.sites < prod.min_sites:
        out.append(f"needs at least {prod.min_sites} sites")
    if prod.requires_gstin and not gst_ok:
        out.append(gst_msg or "needs an active GSTIN")
    return out


def dependency_met(prod: Product, bundle_ids: set[str]) -> bool:
    return not prod.requires_one_of or any(d in bundle_ids for d in prod.requires_one_of)
