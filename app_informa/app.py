import streamlit as st

from app_informa.styles import load_styles
from app_informa.auth import login, register
from profile import get_profile, profile_complete, profile_page
from app_informa.ai import openai_status
from app_informa.pages import dashboard_page, month_calendar_page, weekly_plan_page, export_month_csv

st.set_page_config(page_title="InForma", layout="wide")
load_styles()
st.title("💪 InForma")

# OpenAI key status (safe)
status = openai_status()
if not status["has_key"]:
    st.warning("⚠️ OPENAI_API_KEY non trovata nei Secrets (Streamlit Cloud → Settings → Secrets).")
elif not status["format_ok"]:
    st.warning(f"⚠️ OPENAI_API_KEY trovata da {status['source']} ma formato non valido.")
else:
    st.caption(f"✅ OpenAI key OK (source: {status['source']})")

# Auth
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

    prof = get_profile(uid)
    if not profile_complete(prof):
        st.info("Completa il profilo per iniziare.")
        profile_page(uid)
        st.stop()

    page = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Calendario (mese)", "Piano settimanale", "Export CSV", "Profilo", "Logout"]
    )

    if page == "Dashboard":
        dashboard_page(uid)
    elif page == "Calendario (mese)":
        month_calendar_page(uid)
    elif page == "Piano settimanale":
        weekly_plan_page(uid)
    elif page == "Export CSV":
        export_month_csv(uid)
    elif page == "Profilo":
        profile_page(uid)
    elif page == "Logout":
        del st.session_state.uid
        st.rerun()