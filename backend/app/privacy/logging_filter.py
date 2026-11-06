"""Scrub identifiers out of every log line (application and uvicorn), whatever the caller logged."""
from __future__ import annotations

import logging

from .masking import scrub


class ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = scrub(record.getMessage())
            record.args = ()
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
