import streamlit as st
from datetime import date

from pages.dashboard import render as dashboard_render
from pages.calendar_month import render as calendar_render
from pages.day import render as day_render
from pages.weekly_plan import render as weekly_render
from profile import profile_page

def render(user_id: int):
    page = st.session_state.get("page", "Dashboard")
    if page == "Dashboard":
        dashboard_render(user_id)
    elif page == "Calendario":
        calendar_render(user_id)
    elif page == "Giornata":
        d = st.session_state.get("selected_date", date.today())
        day_render(user_id, d)
    elif page == "Piano settimanale":
        weekly_render(user_id)
    elif page == "Profilo":
        profile_page(user_id)
    else:
        dashboard_render(user_id)
