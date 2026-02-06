import streamlit as st
from auth import login, register
from pages import calendar_page
from profile import profile_page, get_profile
import streamlit as st

# debug “safe”
has_key = False
try:
    has_key = bool(str(st.secrets.get("OPENAI_API_KEY", "")).strip())
except Exception:
    has_key = False

if not has_key:
    st.warning("⚠️ OPENAI_API_KEY non trovata nei Secrets. Vai su Streamlit Cloud → Settings → Secrets e aggiungila.")
st.title("InForma")

if "uid" not in st.session_state:
    email = st.text_input("Email")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        uid = login(email,pwd)
        if uid: st.session_state.uid = uid; st.rerun()
    if st.button("Registrati"):
        register(email,pwd)
        st.success("Creato")
else:
    uid = st.session_state.uid
    if not get_profile(uid):
        profile_page(uid)
        st.stop()

    page = st.sidebar.radio("Menu", ["Calendario","Profilo","Logout"])
    if page=="Calendario": calendar_page(uid)
    if page=="Profilo": profile_page(uid)
    if page=="Logout": del st.session_state.uid; st.rerun()