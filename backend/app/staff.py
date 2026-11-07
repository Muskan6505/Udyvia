"""Staff accounts for the back-office view.   python -m app.staff someone@example.com 'a-long-password'"""
from __future__ import annotations

import sys
import time

from . import auth, db


def ensure_staff(email: str, password: str, name: str = "Back-office") -> None:
    email = email.strip().lower()
    with db.connect() as c:
        row = c.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if row:
            c.execute("UPDATE users SET role='backoffice', pw_hash=? WHERE id=?", (auth.hash_password(password), row["id"]))
        else:
            now = time.time()
            c.execute("INSERT INTO users(email,name,phone,pw_hash,role,created) VALUES(?,?,?,?,?,?)",
                      (email, name, "0000000000", auth.hash_password(password), "backoffice", now))


if __name__ == "__main__":
    if len(sys.argv) != 3 or len(sys.argv[2]) < 10:
        sys.exit("usage: python -m app.staff EMAIL PASSWORD   (password: 10+ characters)")
    db.init()
    ensure_staff(sys.argv[1], sys.argv[2])
    print("staff account ready:", sys.argv[1])
