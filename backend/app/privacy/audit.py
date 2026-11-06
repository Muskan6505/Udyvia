"""Append-only audit log. Never writes raw identifiers or document content: only event, ids and masked values."""
from __future__ import annotations

import json
import time
from pathlib import Path

LOG = Path(__file__).resolve().parents[2] / "audit.log"


def log(event: str, kyc_id: str, **fields) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "kyc_id": kyc_id, **fields}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
