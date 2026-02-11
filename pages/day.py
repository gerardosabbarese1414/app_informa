import streamlit as st
from datetime import date, timedelta

from components.safe import safe_section
from components.planned_section import render as planned_render
from components.actual_section import render as actual_render
from components.meal_forms import render as meal_forms_render
from components.workout_forms import render as workout_forms_render

from db.repo_daylogs import get_day_log, upsert_day_log

def _goto_day(d: date):
    st.session_state.selected_date = d
    st.session_state.page = "Giornata"
    st.rerun()

def render(user_id: int, d: date):
    ds = str(d)
    st.header(f"🗓️ Giornata: {ds}")

    row = get_day_log(user_id, d)
    morning_weight = row["morning_weight"] if row else None
    is_closed = bool(row["is_closed"]) if row else False

    nav1, nav2, nav3 = st.columns([1, 1, 3])
    with nav1:
        if st.button("⬅️ Giorno precedente"):
            _goto_day(d - timedelta(days=1))
    with nav2:
        if st.button("Giorno successivo ➡️"):
            _goto_day(d + timedelta(days=1))

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modificare.")
        if st.button("🔓 Riapri giornata"):
            upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    safe_section("Previsto", lambda: planned_render(user_id, ds, is_closed))
    safe_section("Consuntivo", lambda: actual_render(user_id, ds, is_closed))
    safe_section("Pasti", lambda: meal_forms_render(user_id, ds, is_closed))
    safe_section("Allenamenti", lambda: workout_forms_render(user_id, ds, is_closed))

    st.divider()
    st.subheader("📌 Peso mattutino & chiusura giornata")

    wcol1, wcol2, wcol3 = st.columns([2, 2, 3])
    with wcol1:
        new_w = st.number_input(
            "Peso mattutino (kg)",
            min_value=0.0,
            value=float(morning_weight) if morning_weight is not None else 0.0,
            step=0.1,
            format="%.1f",
            key=f"mw_{ds}",
            disabled=is_closed,
        )
    with wcol2:
        if st.button("💾 Salva peso", key=f"save_mw_{ds}", disabled=is_closed):
            upsert_day_log(user_id, d, morning_weight=float(new_w), is_closed=is_closed)
            st.success("Peso salvato.")
    with wcol3:
        if not is_closed:
            if st.button("✅ Chiudi giornata", key=f"close_day_{ds}"):
                upsert_day_log(user_id, d, morning_weight=float(new_w) if new_w > 0 else morning_weight, is_closed=1)
                st.success("Giornata chiusa ✅")
                st.rerun()
