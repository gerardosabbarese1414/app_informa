import streamlit as st
from datetime import date
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


def _call_page(fn, user_id: int, selected_name: str):
    """
    Chiama la pagina in modo robusto.
    - Per 'Giornata': prova (user_id, date) poi fallback.
    - Per le altre: prova (user_id), poi fallback a ().
    """
    # Caso speciale: Giornata spesso richiede anche una data
    if selected_name == "Giornata":
        d = st.session_state.get("selected_date", date.today())

        # prova firma (user_id, d)
        try:
            return fn(user_id, d)
        except TypeError:
            pass

        # fallback: (user_id)
        try:
            return fn(user_id)
        except TypeError:
            pass

        # fallback: (d)
        try:
            return fn(d)
        except TypeError:
            pass

        # fallback: ()
        return fn()

    # Default: prova (user_id) poi ()
    try:
        sig = inspect.signature(fn)
        n_params = len(sig.parameters)
    except Exception:
        n_params = 1

    if n_params == 0:
        return fn()
    return fn(user_id)


def render(user_id: int):
    # default pagina
    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    # Sidebar menu
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
        # opzionale: pulizia di stato
        st.session_state.pop("selected_date", None)
        st.rerun()

    # Render pagina scelta
    _call_page(PAGES[selected], user_id, selected)