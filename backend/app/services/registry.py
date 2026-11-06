"""Mock GSTIN / Udyam lookup, backed by the CSVs. Swap for a real API behind the same interface."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ..config import DATA_DIR


@lru_cache(maxsize=1)
def _gstin_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "mock_gstin_registry.csv", dtype=str).set_index("gstin", drop=False)


@lru_cache(maxsize=1)
def _udyam_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "mock_udyam_registry.csv", dtype=str).set_index("udyam_number", drop=False)


def lookup_gstin(gstin: str | None) -> dict | None:
    df = _gstin_df()
    return df.loc[gstin].to_dict() if gstin and gstin in df.index else None


def lookup_udyam(number: str | None) -> dict | None:
    df = _udyam_df()
    return df.loc[number].to_dict() if number and number in df.index else None


def gstin_exists(gstin: str) -> bool:
    return gstin in _gstin_df().index
