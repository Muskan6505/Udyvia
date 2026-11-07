"""Accounts: scrypt password hashes, random session tokens (only their SHA-256 is stored), roles.

The token travels in an httpOnly, SameSite=Lax cookie so page scripts can't read it. API clients may
send it as `Authorization: Bearer ...` instead."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time

from fastapi import Depends, HTTPException, Request

from . import db

COOKIE = "udyvia_session"
SESSION_DAYS = 7
MAX_FAILS = 5
LOCK_SECONDS = 600
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^[6-9]\d{9}$")
_FAILS: dict[str, list[float]] = {}       # email -> timestamps of recent failed logins


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got.hex(), h)
    except (ValueError, TypeError):
        return False


def _hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def new_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with db.connect() as c:
        c.execute("INSERT INTO sessions(token_hash,user_id,created,expires) VALUES(?,?,?,?)",
                  (_hash_token(token), user_id, now, now + SESSION_DAYS * 86400))
    return token


def end_session(token: str) -> None:
    with db.connect() as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))


def locked(email: str) -> bool:
    now = time.time()
    recent = [t for t in _FAILS.get(email, []) if now - t < LOCK_SECONDS]
    _FAILS[email] = recent
    return len(recent) >= MAX_FAILS


def record_fail(email: str) -> None:
    _FAILS.setdefault(email, []).append(time.time())


def clear_fails(email: str) -> None:
    _FAILS.pop(email, None)


def _token_from(request: Request) -> str | None:
    h = request.headers.get("authorization", "")
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.cookies.get(COOKIE)


def optional_user(request: Request) -> dict | None:
    token = _token_from(request)
    if not token:
        return None
    with db.connect() as c:
        row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?",
                        (_hash_token(token), time.time())).fetchone()
    return dict(row) if row else None


def current_user(user: dict | None = Depends(optional_user)) -> dict:
    if not user:
        raise HTTPException(401, "Please sign in.")
    return user


def staff_user(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "backoffice":
        raise HTTPException(403, "This area is for Airtel sales and partner staff.")
    return user
