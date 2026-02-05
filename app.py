import streamlit as st
from auth import login, register
from pages import dashboard, calendar, weekly_plan
from styles import load_styles

load_styles()
st.title("💪 Fitness AI")

if "user_id" not in st.session_state:
    tab1, tab2 = st.tabs(["Login", "Registrati"])

    with tab1:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_id = login(email, password)
            if user_id:
                st.session_state.user_id = user_id
                st.rerun()
            else:
                st.error("Credenziali errate")

    with tab2:
        email = st.text_input("Nuova email")
        password = st.text_input("Nuova password", type="password")
        if st.button("Registrati"):
            register(email, password)
            st.success("Account creato, ora fai login")

else:
    page = st.sidebar.radio(
        "Menu",
        ["Dashboard", "Calendario", "Piano Settimanale"]
    )

    if page == "Dashboard":
        dashboard(st.session_state.user_id)
    elif page == "Calendario":
        calendar(st.session_state.user_id)
    else:
        weekly_plan(st.session_state.user_id)

    if st.sidebar.button("Logout"):
        del st.session_state.user_id
        st.rerun()