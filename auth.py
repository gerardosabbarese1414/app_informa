import os
import hashlib
from datetime import datetime
from database import conn


def _hash_password(pw: str) -> str:
    """
    Hash semplice (demo). Per produzione vera: bcrypt/argon2.
    """
    salt = os.getenv("PW_SALT", "change-me-salt")
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()


def create_user(email: str, password: str) -> int:
    """
    Crea utente e ritorna user_id.
    """
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("Email e password obbligatorie")

    h = _hash_password(password)
    conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)",
        (email, h, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()

    row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    return int(row[0])


def verify_login(email: str, password: str) -> int | None:
    """
    Ritorna user_id se credenziali ok, altrimenti None.
    """
    email = (email or "").strip().lower()
    if not email or not password:
        return None

    h = _hash_password(password)
    row = conn.execute(
        "SELECT id FROM users WHERE email=? AND password_hash=?",
        (email, h)
    ).fetchone()
    return int(row[0]) if row else None