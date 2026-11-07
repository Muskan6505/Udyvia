"""Scrub identifiers out of every log line (application and uvicorn), whatever the caller logged."""
from __future__ import annotations

import logging

from .masking import scrub


class ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # Scrub the template and every argument but keep the record's shape: uvicorn's access formatter
            # unpacks exactly five arguments, so emptying them would break its log lines.
            if isinstance(record.msg, str):
                record.msg = scrub(record.msg)
            a = record.args
            if isinstance(a, tuple):
                record.args = tuple(scrub(x) if isinstance(x, str) else x for x in a)
            elif isinstance(a, dict):
                record.args = {k: scrub(v) if isinstance(v, str) else v for k, v in a.items()}
        except Exception:      # never let log scrubbing break a request
            pass
        return True


def install() -> None:
    f = ScrubFilter()
    for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        if not any(isinstance(x, ScrubFilter) for x in lg.filters):
            lg.addFilter(f)
        for h in lg.handlers:
            if not any(isinstance(x, ScrubFilter) for x in h.filters):
                h.addFilter(f)
