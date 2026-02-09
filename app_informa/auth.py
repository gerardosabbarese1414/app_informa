import hashlib
import os
from datetime import datetime
from .database import conn


def _hash_password(pw: str) -> str:
    salt = os.getenv("PW_SALT", "change-me-salt")
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def register(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("Email e password obbligatorie")

    h = _hash_password(password)
    conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)",
        (email, h, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()


def login(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        return None

    h = _hash_password(password)
    row = conn.execute(
        "SELECT id FROM users WHERE email=? AND password_hash=?",
        (email, h)
    ).fetchone()
    return int(row[0]) if row else None