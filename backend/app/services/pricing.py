"""Prices always come from code, never from the LLM."""
from __future__ import annotations

from ..schemas import Product


def unit_price(prod: Product, position: float) -> int:
    position = min(1.0, max(0.0, position))
    return round(prod.price_min + position * (prod.price_max - prod.price_min))


def line_totals(prod: Product, qty: int, position: float) -> tuple[int, int, int]:
    up = unit_price(prod, position)
    return up, up * qty, prod.setup * qty
