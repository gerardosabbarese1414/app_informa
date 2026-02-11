import streamlit as st
import calendar as cal
from datetime import date

from components.safe import safe_section
from db.common import safe_read_sql
from utils import kcal_round

def _day_preview(user_id: int, d: date) -> dict:
    ds = str(d)
    day = safe_read_sql("SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?", (user_id, ds))
    summ = safe_read_sql("SELECT calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date=?", (user_id, ds))
    planned = safe_read_sql("SELECT COUNT(*) AS c FROM planned_events WHERE user_id=? AND date=?", (user_id, ds))

    weight = float(day.iloc[0]["morning_weight"]) if not day.empty and day.iloc[0]["morning_weight"] is not None else None
    closed = bool(day.iloc[0]["is_closed"]) if not day.empty else False
    net = float(summ.iloc[0]["net_calories"]) if not summ.empty and summ.iloc[0]["net_calories"] is not None else None
    planned_count = int(planned.iloc[0]["c"]) if not planned.empty else 0
    return {"weight": weight, "closed": closed, "net": net, "planned": planned_count}

def render(user_id: int):
    st.header("📅 Calendario (mese)")

    # always-available day jump (so calendar rendering can break without blocking the app)
    jump = st.date_input("Vai a un giorno", value=st.session_state.get("selected_date", date.today()))
    if st.button("Apri giornata"):
        st.session_state.selected_date = jump
        st.session_state.page = "Giornata"
        st.rerun()

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        year = int(st.number_input("Anno", 2020, 2100, st.session_state.selected_date.year, 1))
    with c2:
        month = int(st.number_input("Mese", 1, 12, st.session_state.selected_date.month, 1))
    with c3:
        if st.button("📍 Vai a oggi"):
            st.session_state.selected_date = date.today()
            st.rerun()

    headers = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    st.caption("Clicca un giorno → apre la pagina Giornata.")

    # Render with Streamlit grid (robust, no HTML)
    cols = st.columns(7)
    for i, h in enumerate(headers):
        cols[i].markdown(f"**{h}**")

    month_matrix = cal.monthcalendar(year, month)
    today = date.today()

    for week_i, week in enumerate(month_matrix):
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            if day_num == 0:
                cols[i].markdown(" ")
                continue

            d = date(year, month, day_num)
            p = _day_preview(user_id, d)
            is_today = (d == today)

            label = f"{day_num}"
            if p["closed"]:
                label += " ✅"

            # button opens the day (no query params needed)
            if cols[i].button(label, key=f"calbtn_{year}_{month}_{day_num}_{week_i}"):
                st.session_state.selected_date = d
                st.session_state.page = "Giornata"
                st.rerun()

            # small meta
            meta = []
            if p["weight"] is not None:
                meta.append(f"{p['weight']:.1f} kg")
            if p["net"] is not None:
                meta.append(f"NET {kcal_round(p['net'])}")
            if p["planned"] > 0:
                meta.append(f"🗓️ {p['planned']}")
            if meta:
                cols[i].caption(" · ".join(meta))
