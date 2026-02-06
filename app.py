import streamlit as st

from auth import login, register
from pages import calendar_page
from profile import profile_page, get_profile
from ai import openai_status

st.set_page_config(page_title="InForma", layout="centered")
st.title("💪 InForma")

# ===== Debug “safe” OpenAI key =====
status = openai_status()
if not status["has_key"]:
    st.error("❌ OPENAI_API_KEY non trovata. Vai su Streamlit Cloud → Settings → Secrets e aggiungila.")
elif not status["format_ok"]:
    st.error(f"❌ OPENAI_API_KEY trovata da {status['source']} ma formato non valido.")
else:
    st.caption(f"✅ OpenAI key OK (source: {status['source']})")

# ===== AUTH =====
if "uid" not in st.session_state:
    st.subheader("Login / Registrazione")

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("Login"):
            uid = login(email, password)
            if uid:
                st.session_state.uid = uid
                st.rerun()
            else:
                st.error("Credenziali errate")

    with c2:
        if st.button("Registrati"):
            try:
                register(email, password)
                st.success("Account creato ✅ Ora fai login")
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