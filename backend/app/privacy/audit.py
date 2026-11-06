"""Append-only audit trail: who did what, when. Records event names, ids, counts and decisions only.
Never raw identifiers, names, addresses, document content or chat text (values are scrubbed as a backstop)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from .masking import scrub

LOG = Path(os.getenv("AUDIT_LOG_PATH") or Path(__file__).resolve().parents[2] / "audit.log")
_lock = threading.Lock()


def _clean(v):
    if isinstance(v, str):
        return scrub(v)[:200]
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v][:20]
    return scrub(str(v))[:200]


def log(event: str, ref: str | None = None, **fields) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "ref": ref, **{k: _clean(v) for k, v in fields.items()}}
    with _lock:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(LOG, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_all() -> list[dict]:
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
