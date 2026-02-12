import streamlit as st

from styles import load_styles
from database import init_db
from auth_utils import create_user, verify_login
from profile import profile_page, profile_complete
from router import render as route_render


def main():
    st.set_page_config(page_title="InForma", layout="wide")
    load_styles()

    # ✅ DB pronto subito
    init_db()

    if "user_id" not in st.session_state:
        st.session_state.user_id = None

    # --------------------
    # LOGIN / REGISTER
    # --------------------
    if st.session_state.user_id is None:
        st.title("InForma — Login")

        tab1, tab2 = st.tabs(["Login", "Registrati"])
        with tab1:
            email = st.text_input("Email", key="login_email")
            pw = st.text_input("Password", type="password", key="login_pw")
            if st.button("Entra", type="primary"):
                uid = verify_login(email, pw)
                if uid:
                    st.session_state.user_id = uid
                    st.rerun()
                else:
                    st.error("Credenziali non valide.")

        with tab2:
            email = st.text_input("Email", key="reg_email")
            pw = st.text_input("Password", type="password", key="reg_pw")
            if st.button("Crea account", type="primary"):
                try:
                    uid = create_user(email, pw)
                    st.session_state.user_id = uid
                    st.success("Account creato ✅")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        return

    uid = st.session_state.user_id

    # --------------------
    # PROFILO OBBLIGATORIO
    # --------------------
    if not profile_complete(uid):
        profile_page(uid)
        return

    # --------------------
    # ROUTER
    # --------------------
    route_render(uid)


if __name__ == "__main__":
    main()