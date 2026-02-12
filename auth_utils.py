import os
import hashlib
import sqlite3
from datetime import datetime

from database import conn, init_db


def _hash_password(pw: str) -> str:
    salt = os.getenv("PW_SALT", "change-me-salt")
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def create_user(email: str, password: str) -> int:
    init_db()

    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("Email e password obbligatorie")

    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        raise ValueError("Email già registrata. Prova il login.")

    conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)",
        (email, _hash_password(password), datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()

    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return int(row["id"])


def verify_login(email: str, password: str) -> int | None:
    init_db()

    email = (email or "").strip().lower()
    if not email or not password:
        return None

    try:
        row = conn.execute(
            "SELECT id FROM users WHERE email=? AND password_hash=?",
            (email, _hash_password(password))
        ).fetchone()
    except sqlite3.OperationalError:
        # se il DB era vuoto / tabelle non presenti (reset container)
        init_db()
        row = conn.execute(
            "SELECT id FROM users WHERE email=? AND password_hash=?",
            (email, _hash_password(password))
        ).fetchone()

    return int(row["id"]) if row else None