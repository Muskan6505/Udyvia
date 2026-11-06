"""Loads the catalogue and registries once at startup (CSV -> memory)."""
from __future__ import annotations

import csv
from functools import lru_cache

from ..config import DATA_DIR
from ..schemas import Product


def _split(v: str, sep: str) -> list[str]:
    return [x for x in (v or "").split(sep) if x]


@lru_cache(maxsize=1)
def catalogue() -> dict[str, Product]:
    out: dict[str, Product] = {}
    with open(DATA_DIR / "product_catalogue.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["product_id"]] = Product(
                product_id=r["product_id"],
                category=r["category"],
                product_name=r["product_name"],
                description=r["description"],
                unit=r["unit"],
                price_min=int(r["price_min_inr_per_month"]),
                price_max=int(r["price_max_inr_per_month"]),
                setup=int(r["one_time_setup_inr"]),
                min_contract_months=int(r["min_contract_months"]),
                city_tiers=[int(x) for x in _split(r["available_city_tiers"], ";")],
                min_employees=int(r["min_employees"]),
                min_sites=int(r["min_sites"]),
                requires_gstin=r["requires_gstin"] == "Y",
                requires_one_of=_split(r["requires_one_of"], "|"),
                install_days=int(r["typical_install_days"]),
                target_segments=_split(r["target_segments"], ";"),
            )
    return out


@lru_cache(maxsize=1)
def gstin_registry() -> dict[str, dict]:
    with open(DATA_DIR / "mock_gstin_registry.csv", newline="", encoding="utf-8") as f:
        return {r["gstin"]: r for r in csv.DictReader(f)}


def gstin_status(gstin: str | None) -> str:
    """Active | Cancelled | Suspended | Unknown (not in registry) | None (no number)."""
    if not gstin:
        return "None"
    rec = gstin_registry().get(gstin.strip().upper())
    return rec["status"] if rec else "Unknown"


@lru_cache(maxsize=1)
def city_tiers() -> dict[str, int]:
    """City -> tier, as seen in the leads data (22 cities)."""
    out: dict[str, int] = {}
    with open(DATA_DIR / "smb_leads.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["city"], int(r["city_tier"]))
    return out


@lru_cache(maxsize=1)
def business_types() -> list[str]:
    with open(DATA_DIR / "smb_leads.csv", newline="", encoding="utf-8") as f:
        return sorted({r["business_type"] for r in csv.DictReader(f)})
