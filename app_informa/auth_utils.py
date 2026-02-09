import os
import hashlib
from datetime import datetime
from database import conn


def _hash_password(pw: str) -> str:
    salt = os.getenv("PW_SALT", "change-me-salt")
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def create_user(email: str, password: str) -> int:
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
    email = (email or "").strip().lower()
    if not email or not password:
        return None
    row = conn.execute(
        "SELECT id FROM users WHERE email=? AND password_hash=?",
        (email, _hash_password(password))
    ).fetchone()
    return int(row["id"]) if row else None