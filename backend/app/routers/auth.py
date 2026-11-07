"""Sign up, sign in, sign out, delete my account."""
from __future__ import annotations

import os
import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import auth, db
from ..privacy import audit
from ..services import journey

router = APIRouter(prefix="/auth", tags=["auth"])
GENERIC_FAIL = "That email and password don't match."


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=320)
    phone: str
    password: str = Field(min_length=8, max_length=128)
    contact_consent: bool = False          # may Airtel call me about my application?


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                    secure=os.getenv("COOKIE_SECURE", "0") == "1", path="/")


def _me(u: dict) -> dict:
    return dict(id=u["id"], name=u["name"], email=u["email"], phone=u["phone"], role=u["role"],
                contact_consent=bool(u["contact_consent"]))


@router.post("/register", status_code=201)
def register(body: RegisterIn, response: Response):
    email = body.email.strip().lower()
    phone = "".join(ch for ch in body.phone if ch.isdigit())[-10:]
    if not auth.EMAIL_RE.match(email):
        raise HTTPException(422, "Please enter a valid email address.")
    if not auth.PHONE_RE.match(phone):
        raise HTTPException(422, "Please enter a 10-digit mobile number.")
    now = time.time()
    try:
        with db.connect() as c:
            cur = c.execute("INSERT INTO users(email,name,phone,pw_hash,contact_consent,consent_at,created,last_login) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (email, body.name.strip(), phone, auth.hash_password(body.password), int(body.contact_consent),
                             now if body.contact_consent else None, now, now))
            uid = cur.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Try signing in.")
    journey.ensure(uid)
    audit.log("account_created", str(uid), contact_consent=body.contact_consent)
    _set_cookie(response, auth.new_session(uid))
    with db.connect() as c:
        return _me(dict(c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()))


@router.post("/login")
def login(body: LoginIn, response: Response):
    email = body.email.strip().lower()
    if auth.locked(email):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    with db.connect() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    # verify even when the email is unknown, so timing doesn't reveal which emails have accounts
    ok = auth.verify_password(body.password, r["pw_hash"] if r else "scrypt$00$00")
    if not r or not ok:
        auth.record_fail(email)
        audit.log("login_failed", "-")
        raise HTTPException(401, GENERIC_FAIL)
    auth.clear_fails(email)
    with db.connect() as c:
        c.execute("UPDATE users SET last_login=? WHERE id=?", (time.time(), r["id"]))
    _set_cookie(response, auth.new_session(r["id"]))
    audit.log("login", str(r["id"]), role=r["role"])
    return _me(dict(r))


@router.post("/logout")
def logout(request: Request, response: Response):
    token = auth._token_from(request)
    if token:
        auth.end_session(token)
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    return _me(user)


@router.put("/me/contact-consent")
def set_consent(body: dict, user: dict = Depends(auth.current_user)):
    on = bool(body.get("contact_consent"))
    with db.connect() as c:
        c.execute("UPDATE users SET contact_consent=?, consent_at=? WHERE id=?", (int(on), time.time() if on else None, user["id"]))
    audit.log("contact_consent_changed", str(user["id"]), on=on)
    return {"contact_consent": on}


@router.delete("/account")
def delete_account(response: Response, user: dict = Depends(auth.current_user)):
    """Erases the account and everything saved against it: the journey, orders and sign-in sessions."""
    from . import orders
    uid = user["id"]
    with db.connect() as c:
        mine = [r["order_id"] for r in c.execute("SELECT order_id FROM orders WHERE user_id=?", (uid,))]
        c.execute("DELETE FROM users WHERE id=?", (uid,))          # cascades to sessions, journeys, orders
    for oid in mine:
        orders._ORDERS.pop(oid, None)
    response.delete_cookie(auth.COOKIE, path="/")
    audit.log("account_deleted", str(uid), orders=len(mine))
    return {"deleted": True}
