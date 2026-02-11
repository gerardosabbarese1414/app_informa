import streamlit as st
    from datetime import date, timedelta, datetime

    from db.common import safe_read_sql
    from database import conn
    from profile import get_profile
    from ai import generate_weekly_plan, explain_openai_error
    from utils import iso_year_week, bmr_mifflin, tdee_from_level, heuristic_workout_kcal

    def _daily_target_kcal(profile: dict, rest_kcal: float) -> float:
        goal_type = str(profile.get("goal_type") or "mantenimento").lower()
        if "dimagr" in goal_type or "deficit" in goal_type:
            return max(rest_kcal - 500, 1200)
        if "massa" in goal_type or "surplus" in goal_type:
            return rest_kcal + 250
        return rest_kcal

    def _apply_plan_to_calendar(user_id: int, week_start: date, plan_text: str, workout_slots):
        prof = get_profile(user_id) or {}
        weight = float(prof.get("start_weight") or 75.0)
        height = float(prof.get("height_cm") or 175.0)
        sex = (prof.get("sex") or "M")
        age = int(prof.get("age") or 25)
        act = (prof.get("activity_level") or "leggero").lower()

        bmr = bmr_mifflin(sex, weight, height, age)
        rest = tdee_from_level(bmr, act)
        target_in = _daily_target_kcal(prof, rest)

        meal_slots = [
            ("08:00", "Colazione (piano)", 0.25),
            ("13:00", "Pranzo (piano)", 0.35),
            ("17:00", "Spuntino (piano)", 0.10),
            ("20:30", "Cena (piano)", 0.30),
        ]

        week_end = week_start + timedelta(days=6)

        conn.execute("DELETE FROM planned_events WHERE user_id=? AND date>=? AND date<=?",
                     (user_id, str(week_start), str(week_end)))
        conn.commit()

        note = (plan_text or "").strip()
        if len(note) > 350:
            note = note[:350] + "…"

        for i in range(7):
            d = week_start + timedelta(days=i)
            ds = str(d)
            for t, title, pct in meal_slots:
                kcal = float(target_in * pct)
                conn.execute(
                    """
                    INSERT INTO planned_events
                      (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (user_id, ds, t, "meal", title, kcal, None, "planned", note)
                )

        if workout_slots:
            for slot in workout_slots:
                ds = slot["date"]
                time_str = slot.get("time", "19:00")
                title = slot.get("title", "Allenamento")
                dur = int(slot.get("duration_min") or 0)
                kcal_burn = float(heuristic_workout_kcal(title, dur))
                conn.execute(
                    """
                    INSERT INTO planned_events
                      (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (user_id, ds, time_str, "workout", title, kcal_burn, dur if dur>0 else None, "planned", "Allenamento pianificato")
                )
        conn.commit()

    def render(user_id: int):
        st.header("🧠 Piano settimanale → Inserisci nel calendario (previsto)")

        today = date.today()
        default_start = today + timedelta(days=(7 - today.weekday()) % 7)  # prossimo lunedì
        week_start = st.date_input("Settimana da pianificare (lunedì)", value=default_start)

        st.subheader("Allenamenti previsti (scegli tu giorni e orari)")
        if "workout_slots" not in st.session_state:
            st.session_state.workout_slots = [
                {"date": str(week_start), "time": "19:00", "title": "Pesi", "duration_min": 60},
                {"date": str(week_start + timedelta(days=2)), "time": "19:00", "title": "Cardio", "duration_min": 40},
            ]

        slots = st.session_state.workout_slots
        slots = st.data_editor(slots, num_rows="dynamic", use_container_width=True)
        st.session_state.workout_slots = slots

        prof = get_profile(user_id) or {}
        prev_start = week_start - timedelta(days=7)
        prev_end = week_start - timedelta(days=1)
        last_week_sums = safe_read_sql(
            "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date>=? AND date<=? ORDER BY date",
            (user_id, str(prev_start), str(prev_end))
        )

        y, w = iso_year_week(week_start)
        existing = conn.execute(
            "SELECT content, created_at FROM weekly_plan WHERE user_id=? AND iso_year=? AND iso_week=?",
            (user_id, y, w)
        ).fetchone()

        if existing:
            st.caption(f"Piano già generato (cache) — {existing['created_at']}")
            st.markdown(existing["content"])
            if st.button("Re-inserisci eventi nel calendario (previsto)"):
                _apply_plan_to_calendar(user_id, week_start, existing["content"], st.session_state.workout_slots)
                st.success("Eventi previsti inseriti nel calendario ✅")
            if st.button("Rigenera piano (nuova chiamata)"):
                existing = None

        if not existing:
            if st.button("🔄 Genera piano + Inserisci nel calendario"):
                prompt = f"""Sei un coach nutrizionale/fitness. Crea un piano settimanale pratico e sostenibile.
Settimana start (lunedì): {week_start}
Profilo: {prof}
Allenamenti previsti: {st.session_state.workout_slots}
Ultima settimana (riassunto): {last_week_sums.to_dict(orient='records') if not last_week_sums.empty else 'nessun dato'}
Scrivi un piano giorno-per-giorno (Lun→Dom) con pasti e kcal.
"""
                with st.spinner("Genero piano..."):
                    try:
                        content = generate_weekly_plan(prompt)
                    except Exception as e:
                        st.error(explain_openai_error(e))
                        return

                conn.execute(
                    "INSERT INTO weekly_plan (user_id, iso_year, iso_week, content, created_at) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(user_id, iso_year, iso_week) DO UPDATE SET content=excluded.content, created_at=excluded.created_at",
                    (user_id, y, w, content, datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()

                _apply_plan_to_calendar(user_id, week_start, content, st.session_state.workout_slots)
                st.success("Piano generato e inserito nel calendario ✅")
                st.rerun()
