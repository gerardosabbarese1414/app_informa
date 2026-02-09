import streamlit as st
from datetime import date

from styles import load_styles
from auth import create_user, verify_login
from profile import profile_page, profile_complete
from pages import dashboard_page, month_calendar_page, day_page, weekly_plan_page


def main():
    st.set_page_config(page_title="InForma", layout="wide")
    load_styles()
    st.title("💪 InForma")

    if "uid" not in st.session_state:
        st.session_state.uid = None
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    # LOGIN / REGISTRAZIONE
    if st.session_state.uid is None:
        st.subheader("🔐 Login / Registrazione")
        t1, t2 = st.tabs(["Login", "Registrati"])

        with t1:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            if st.button("Login", type="primary"):
                uid = verify_login(email, password)
                if uid:
                    st.session_state.uid = uid
                    st.rerun()
                else:
                    st.error("Credenziali errate")

        with t2:
            email2 = st.text_input("Email", key="reg_email")
            pw2 = st.text_input("Password", type="password", key="reg_pw")
            if st.button("Crea account"):
                try:
                    uid = create_user(email2, pw2)
                    st.success("Account creato ✅ Ora completa il profilo.")
                    st.session_state.uid = uid
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        return

    uid = st.session_state.uid

    # PROFILO OBBLIGATORIO
    if not profile_complete(uid):
        profile_page(uid)
        return

    # SIDEBAR
    with st.sidebar:
        st.subheader("📌 Menu")
        page = st.radio(
            "Sezione",
            ["Dashboard", "Calendario", "Giornata", "Piano settimanale", "Profilo", "Logout"]
        )
        st.session_state.page = page

    page = st.session_state.page

    if page == "Dashboard":
        dashboard_page(uid)
    elif page == "Calendario":
        month_calendar_page(uid)
    elif page == "Giornata":
        day_page(uid, st.session_state.selected_date)
    elif page == "Piano settimanale":
        weekly_plan_page(uid)
    elif page == "Profilo":
        profile_page(uid)
    elif page == "Logout":
        st.query_params.clear()
        st.session_state.uid = None
        st.rerun()


if __name__ == "__main__":
    main()