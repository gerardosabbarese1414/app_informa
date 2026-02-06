import streamlit as st

from auth import login, register
from pages import calendar_page
from profile import profile_page, get_profile

st.set_page_config(page_title="InForma", layout="centered")
st.title("💪 InForma")

# ===== DEBUG API KEY (safe) =====
has_key = False
try:
    has_key = bool(str(st.secrets.get("OPENAI_API_KEY", "")).strip())
except Exception:
    has_key = False

if not has_key:
    st.warning("⚠️ OPENAI_API_KEY non trovata. Aggiungila in Streamlit → Settings → Secrets.")

# ===== AUTH =====
if "uid" not in st.session_state:
    st.subheader("Login / Registrazione")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            uid = login(email, password)
            if uid:
                st.session_state.uid = uid
                st.rerun()
            else:
                st.error("Credenziali errate")

    with col2:
        if st.button("Registrati"):
            try:
                register(email, password)
                st.success("Account creato, ora fai login")
            except Exception:
                st.error("Errore creazione account (email già usata?)")

else:
    uid = st.session_state.uid

    # ===== ONBOARDING PROFILO =====
    profile = get_profile(uid)
    if not profile:
        st.info("Completa il profilo per iniziare")
        profile_page(uid)
        st.stop()

    # ===== MENU =====
    page = st.sidebar.radio("Menu", ["Calendario", "Profilo", "Logout"])

    if page == "Calendario":
        calendar_page(uid)

    elif page == "Profilo":
        profile_page(uid)

    elif page == "Logout":
        del st.session_state.uid
        st.rerun()