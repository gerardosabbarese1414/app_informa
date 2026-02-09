import streamlit as st
from datetime import date

from styles import load_styles
from database import init_db
from auth_utils import create_user, verify_login
from profile import profile_page, profile_complete
from pages import dashboard_page, month_calendar_page, weekly_plan_page, day_page


def main():
    st.set_page_config(page_title="InForma", layout="wide")
    load_styles()

    # ✅ IMPORTANTISSIMO: crea tabelle se non esistono
    init_db()

    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"
    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

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
    # SIDEBAR NAV
    # --------------------
    with st.sidebar:
        st.title("InForma")

        # ✅ Nota: NON includiamo "Giornata" nel menu, ma impediamo che venga sovrascritta
        menu_pages = ["Dashboard", "Calendario", "Piano settimanale", "Profilo"]

        # se siamo in "Giornata", lasciamo invariato session_state.page (non radio)
        if st.session_state.page in menu_pages:
            page = st.radio(
                "Menu",
                menu_pages,
                index=menu_pages.index(st.session_state.page),
            )
            st.session_state.page = page
        else:
            # pagina "speciale" (es. Giornata) -> mostro solo un'indicazione e un tasto per tornare
            st.caption(f"Pagina: **{st.session_state.page}**")
            if st.button("⬅️ Torna al Calendario"):
                st.session_state.page = "Calendario"
                st.rerun()

        st.divider()
        if st.button("Logout"):
            st.session_state.user_id = None
            st.rerun()

    # --------------------
    # ROUTING PAGES
    # --------------------
    if st.session_state.page == "Dashboard":
        dashboard_page(uid)

    elif st.session_state.page == "Calendario":
        month_calendar_page(uid)

    elif st.session_state.page == "Piano settimanale":
        weekly_plan_page(uid)

    elif st.session_state.page == "Profilo":
        profile_page(uid)

    elif st.session_state.page == "Giornata":
        # ✅ la "Giornata" ora esiste davvero
        day_page(uid, st.session_state.selected_date)

    else:
        st.warning(f"Pagina sconosciuta: {st.session_state.page}")
        st.session_state.page = "Dashboard"
        st.rerun()


if __name__ == "__main__":
    main()