import streamlit as st
from styles import load_styles
from auth import login, register
from pages import dashboard, month_calendar, weekly_plan_page

load_styles()
st.title("💪 InForma — Fitness AI")

if "user_id" not in st.session_state:
    tab1, tab2 = st.tabs(["Login", "Registrati"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            uid = login(email, password)
            if uid:
                st.session_state.user_id = uid
                st.rerun()
            else:
                st.error("Credenziali errate")

    with tab2:
        email2 = st.text_input("Nuova email")
        password2 = st.text_input("Nuova password", type="password")
        if st.button("Registrati"):
            try:
                register(email2, password2)
                st.success("Account creato ✅ Ora fai login")
            except Exception:
                st.error("Email già usata o errore creazione account")
else:
    st.sidebar.title("Menu")
    page = st.sidebar.radio("", ["Dashboard", "Calendario (mese)", "Piano settimanale"])

    if page == "Dashboard":
        dashboard(st.session_state.user_id)
    elif page == "Calendario (mese)":
        month_calendar(st.session_state.user_id)
    else:
        weekly_plan_page(st.session_state.user_id)

    if st.sidebar.button("Logout"):
        del st.session_state.user_id
        st.rerun()