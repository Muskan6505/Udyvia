from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Product(BaseModel):
    product_id: str
    category: str
    product_name: str
    description: str
    unit: str
    price_min: int
    price_max: int
    setup: int
    min_contract_months: int
    city_tiers: list[int]
    min_employees: int
    min_sites: int
    requires_gstin: bool
    requires_one_of: list[str]
    install_days: int
    target_segments: list[str]

    @property
    def is_connectivity(self) -> bool:
        return self.category == "Connectivity" and not self.requires_one_of and self.product_id not in ("P07", "P08")


class Profile(BaseModel):
    """Slots the advisor fills. The rules engine consumes only this."""
    business_type: str = ""
    segment: Optional[str] = None            # explicit override; else derived
    employees: int = Field(ge=1)
    sites: int = Field(default=1, ge=1)
    city: str = ""
    city_tier: int = Field(ge=1, le=2)
    gstin: Optional[str] = None              # looked up in the registry for status
    has_gstin: Optional[bool] = None         # used when no number is given yet
    current_internet: Optional[str] = None
    needs: list[str] = []                    # free keywords or product ids
    budget_monthly: Optional[int] = None


class QuoteLine(BaseModel):
    product_id: str
    product_name: str
    unit: str
    qty: int
    unit_price: int
    line_monthly: int
    line_setup: int
    included: bool = True
    role: str = "core"          # core | need | addon | dependency
    reason: str = ""


class Blocked(BaseModel):
    product_id: str
    product_name: str
    reasons: list[str]
    alternative: Optional[str] = None   # product id that can be offered instead
    upgrade_path: str = ""


class Quote(BaseModel):
    quote_id: str
    segment: str
    profile: Profile
    gstin_status: str                    # Active | Cancelled | Suspended | Unknown | None
    lines: list[QuoteLine]
    monthly_total: int
    setup_total: int
    contract_months: int
    expected_install_days: int
    price_position: float
    within_budget: Optional[bool] = None
    blocked: list[Blocked] = []
    notes: list[str] = []
    kyc_decision: Optional[str] = None


class AddonChange(BaseModel):
    product_id: str
    included: bool = True
    qty: Optional[int] = Field(default=None, ge=1)
