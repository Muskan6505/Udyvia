"""SQLite storage for accounts and the journey each person has made through the flow.

Only what is needed to resume and follow up is stored here. Document images, OCR text and the
signatory's ID details never reach this database (they stay in the 24-hour KYC store)."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "var" / "udyvia.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  pw_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'customer',
  contact_consent INTEGER NOT NULL DEFAULT 0,
  consent_at REAL,
  is_demo INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  last_login REAL
);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created REAL NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS journeys(
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  stage TEXT NOT NULL DEFAULT 'registered',
  lang TEXT NOT NULL DEFAULT 'en',
  slots TEXT NOT NULL DEFAULT '{}',
  selections TEXT NOT NULL DEFAULT '{}',
  price_position REAL,
  gst_status TEXT,
  kyc_decision TEXT,
  quote_id TEXT,
  kyc_session_id TEXT,
  order_id TEXT,
  segment TEXT,
  monthly_total INTEGER,
  setup_total INTEGER,
  within_budget INTEGER,
  blocked_count INTEGER NOT NULL DEFAULT 0,
  payment_failures INTEGER NOT NULL DEFAULT 0,
  closed INTEGER NOT NULL DEFAULT 0,
  follow_up_status TEXT NOT NULL DEFAULT 'new',
  follow_up_note TEXT NOT NULL DEFAULT '',
  followed_up_at REAL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders(
  order_id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  data TEXT NOT NULL,
  updated REAL NOT NULL
);
"""


def path() -> Path:
    return Path(os.getenv("UDYVIA_DB", str(DEFAULT_PATH)))


def init() -> None:
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with connect() as c:
        c.executescript(SCHEMA)
    if new:
        try:
            os.chmod(p, 0o600)          # owner-only on Linux/macOS; Windows relies on the user folder's ACL
        except OSError:
            pass


@contextmanager
def connect():
    c = sqlite3.connect(path(), timeout=10)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()
