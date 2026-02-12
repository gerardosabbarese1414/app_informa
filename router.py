import streamlit as st

from views.dashboard import render as dashboard_render
from views.calendar_month import render as calendar_render
from views.day import render as day_render
from views.weekly_plan import render as weekly_render
from profile import profile_page

PAGES = {
    "Dashboard": dashboard_render,
    "Calendario": calendar_render,
    "Giornata": day_render,
    "Piano settimanale": weekly_render,
    "Profilo": profile_page,
}

def render(user_id: int):
    # ✅ default pagina
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    # ✅ sidebar sempre visibile (perché sempre piena)
    st.sidebar.title("InForma")
    selected = st.sidebar.radio(
        "Menu",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(st.session_state.page)
        if st.session_state.page in PAGES else 0
    )
    st.session_state.page = selected

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.page = "Dashboard"
        st.rerun()

    # ✅ render pagina scelta
    PAGES[selected](user_id)