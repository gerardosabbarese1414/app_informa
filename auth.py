import hashlib
import os
from datetime import datetime
import streamlit as st
from database import conn


def _hash_password(pw: str) -> str:
    salt = os.getenv("PW_SALT", "change-me-salt")
    return hashlib.sha256((salt + (pw or "")).encode("utf-8")).hexdigest()


def register_user(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        raise ValueError("Email e password obbligatorie")

    h = _hash_password(password)
    conn.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?,?,?)",
        (email, h, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()


def login_user(email: str, password: str):
    email = (email or "").strip().lower()
    if not email or not password:
        return None

    h = _hash_password(password)
    row = conn.execute(
        "SELECT id FROM users WHERE email=? AND password_hash=?",
        (email, h)
    ).fetchone()
    return int(row[0]) if row else None


def login_page():
    st.subheader("🔐 Login")
    email = st.text_input("Email", key="login_email")
    pw = st.text_input("Password", type="password", key="login_pw")

    if st.button("Login", type="primary"):
        uid = login_user(email, pw)
        if uid:
            st.session_state.user_id = uid
            st.rerun()
        st.error("Credenziali errate.")


def register_page():
    st.subheader("🧾 Registrazione")
    email = st.text_input("Email", key="reg_email")
    pw = st.text_input("Password", type="password", key="reg_pw")

    if st.button("Crea account"):
        try:
            register_user(email, pw)
            st.success("Account creato ✅ Ora fai login.")
        except Exception as e:
            st.error(str(e))