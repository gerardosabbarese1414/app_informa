import streamlit as st
import inspect

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

def _call_page(fn, user_id: int):
    """Chiama fn() o fn(user_id) a seconda della firma."""
    try:
        sig = inspect.signature(fn)
        n_params = len(sig.parameters)
    except Exception:
        # fallback: prova con user_id
        n_params = 1

    if n_params == 0:
        return fn()
    else:
        return fn(user_id)

def render(user_id: int):
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    st.sidebar.title("InForma")
    keys = list(PAGES.keys())

    selected = st.sidebar.radio(
        "Menu",
        keys,
        index=keys.index(st.session_state.page) if st.session_state.page in keys else 0
    )
    st.session_state.page = selected

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.page = "Dashboard"
        st.rerun()

    _call_page(PAGES[selected], user_id)