import streamlit as st
import pandas as pd
import plotly.express as px
import calendar as cal
from datetime import date, datetime, timedelta

from database import conn
from profile import get_profile
from utils import bmr_mifflin, tdee_from_level, iso_year_week, kcal_round, heuristic_workout_kcal
from ai import (
    analyze_food_photo,
    estimate_meal_from_text,
    estimate_workout_from_text,
    generate_weekly_plan,
    explain_openai_error,
)


# ----------------------------
# SQL helpers
# ----------------------------
def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()


def goto_day(d: date):
    st.session_state.selected_date = d
    st.session_state.page = "Giornata"
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()


# ----------------------------
# day log helpers
# ----------------------------
def upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    ds = str(d)
    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    if row:
        mw = morning_weight if morning_weight is not None else row["morning_weight"]
        ic = int(is_closed) if is_closed is not None else row["is_closed"]
        conn.execute(
            "UPDATE day_logs SET morning_weight=?, is_closed=? WHERE user_id=? AND date=?",
            (mw, ic, user_id, ds)
        )
    else:
        conn.execute(
            "INSERT INTO day_logs (user_id, date, morning_weight, is_closed) VALUES (?,?,?,?)",
            (user_id, ds, morning_weight, int(is_closed or 0))
        )
    conn.commit()


def fetch_day_preview(user_id: int, d: date):
    ds = str(d)
    day = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    summ = conn.execute(
        "SELECT calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    planned_count = conn.execute(
        "SELECT COUNT(*) AS c FROM planned_events WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()["c"]

    return {
        "weight": day["morning_weight"] if day else None,
        "closed": bool(day["is_closed"]) if day else False,
        "in": summ["calories_in"] if summ else None,
        "out": summ["calories_out"] if summ else None,
        "net": summ["net_calories"] if summ else None,
        "planned": planned_count,
    }


# ----------------------------
# Planned events
# ----------------------------
def planned_for_day(user_id: int, d: date) -> pd.DataFrame:
    ds = str(d)
    return safe_read_sql(
        """
        SELECT id, time, type, title, expected_calories, duration_min, status, notes
        FROM planned_events
        WHERE user_id=? AND date=?
        ORDER BY time
        """,
        (user_id, ds)
    )


def add_planned_event(
    user_id: int,
    d: date,
    time_str: str,
    typ: str,
    title: str,
    expected_calories: float | None,
    duration_min: int | None,
    notes: str | None,
):
    ds = str(d)
    conn.execute(
        """
        INSERT INTO planned_events
          (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (user_id, ds, time_str, typ, title, expected_calories, duration_min, "planned", notes)
    )
    conn.commit()


def delete_planned_event(user_id: int, planned_id: int):
    conn.execute("DELETE FROM planned_events WHERE user_id=? AND id=?", (user_id, planned_id))
    conn.commit()


def mark_planned_done_to_actual(user_id: int, d: date, planned_row: dict):
    ds = str(d)
    typ = planned_row.get("type")

    if typ == "meal":
        conn.execute(
            "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
            (
                user_id, ds,
                planned_row.get("time"),
                f"[Previsto] {planned_row.get('title')}",
                float(planned_row.get("expected_calories") or 0),
                None
            )
        )
    elif typ == "workout":
        conn.execute(
            """
            INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                user_id, ds,
                planned_row.get("time"),
                f"[Previsto] {planned_row.get('title')}",
                int(planned_row.get("duration_min") or 0),
                float(planned_row.get("expected_calories") or 0),
                None
            )
        )

    conn.execute(
        "UPDATE planned_events SET status='done' WHERE user_id=? AND id=?",
        (user_id, int(planned_row["id"]))
    )
    conn.commit()


# ----------------------------
# Dashboard
# ----------------------------
def dashboard_page(user_id: int):
    st.header("📊 Dashboard")

    weights = safe_read_sql(
        "SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND morning_weight IS NOT NULL ORDER BY date",
        (user_id,)
    )
    sums = safe_read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? ORDER BY date",
        (user_id,)
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Peso ultimo", f"{weights.iloc[-1]['weight']:.1f} kg" if not weights.empty else "—")
    c2.metric("NET ultimo giorno", f"{kcal_round(sums.iloc[-1]['net_calories'])} kcal" if not sums.empty else "—")
    c3.metric("Giorni chiusi", f"{len(sums)}")

    if not weights.empty:
        st.plotly_chart(px.line(weights, x="date", y="weight", title="Peso nel tempo"), use_container_width=True)

    if not sums.empty:
        st.plotly_chart(
            px.bar(sums.tail(30), x="date", y=["calories_in", "calories_out"], barmode="group",
                   title="Calorie IN/OUT (ultimi 30 giorni)"),
            use_container_width=True
        )
        st.plotly_chart(px.line(sums.tail(30), x="date", y="net_calories", title="NET (ultimi 30 giorni)"),
                        use_container_width=True)


# ----------------------------
# Month calendar (Google-like)
# ----------------------------
def month_calendar_page(user_id: int):
    st.header("📅 Calendario (mese)")

    # routing da link
    try:
        qp = st.query_params
        if qp.get("view") == "day" and qp.get("date"):
            goto_day(date.fromisoformat(str(qp.get("date"))))
    except Exception:
        pass

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

    month_matrix = cal.monthcalendar(year, month)
    headers = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

    st.caption("Clicca una cella (stile Google Calendar) → apre il giorno con compilazione.")

    st.markdown('<div class="cal-wrap">', unsafe_allow_html=True)
    st.markdown(
        '<div class="cal-head">' + "".join([f"<div>{h}</div>" for h in headers]) + "</div>",
        unsafe_allow_html=True
    )

    cells = ['<div class="cal-grid">']
    today = date.today()

    for week in month_matrix:
        for day_num in week:
            if day_num == 0:
                cells.append('<div class="cal-empty"></div>')
                continue

            d = date(year, month, int(day_num))
            p = fetch_day_preview(user_id, d)

            badge = "✅" if p["closed"] else "•"
            color_cls = ""
            if p["net"] is not None:
                if p["net"] <= 0:
                    color_cls = "badge-ok"
                elif p["net"] <= 300:
                    color_cls = "badge-warn"
                else:
                    color_cls = "badge-bad"

            planned_preview = safe_read_sql(
                """
                SELECT time, type, title, expected_calories
                FROM planned_events
                WHERE user_id=? AND date=?
                ORDER BY time
                LIMIT 2
                """,
                (user_id, str(d))
            )

            meta_lines = []
            if p["weight"] is not None:
                meta_lines.append(f"{float(p['weight']):.1f} kg")
            if p["net"] is not None:
                meta_lines.append(f"<span class='{color_cls}'>NET {kcal_round(p['net'])}</span>")
            if p["planned"] > 0:
                meta_lines.append(f"🗓️ {p['planned']} prev.")

            mini = []
            if not planned_preview.empty:
                for _, r in planned_preview.iterrows():
                    tag = "🍽️" if r["type"] == "meal" else "🏃"
                    kcal = f"~{kcal_round(r['expected_calories'])}kcal" if pd.notna(r["expected_calories"]) else ""
                    mini.append(f"<div>{tag} {r['time']} {kcal}</div>")

            is_today_cls = " cal-today" if d == today else ""
            href = f"?view=day&date={d.isoformat()}"

            # ✅ FIX: niente triple-quote indentate (altrimenti Streamlit lo stampa come codice)
            cell_html = (
                f'<a class="cal-cell{is_today_cls}" href="{href}">'
                f'  <div class="cal-top">'
                f'    <div class="cal-daynum">{day_num}</div>'
                f'    <div class="cal-dot">{badge}</div>'
                f'  </div>'
                f'  <div class="cal-meta">'
                f'    {("<br>".join(meta_lines) if meta_lines else "&nbsp;")}'
                f'  </div>'
                f'  <div class="cal-mini">'
                f'    {("".join(mini) if mini else "")}'
                f'  </div>'
                f'</a>'
            )
            cells.append(cell_html)

    cells.append("</div></div>")
    st.markdown("".join(cells), unsafe_allow_html=True)


# ----------------------------
# Day page (Giornata) - CON TESTO + FOTO
# ----------------------------
def day_page(user_id: int, d: date):
    ds = str(d)
    st.header(f"🗓️ Giornata: {ds}")

    # stato giorno
    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()
    morning_weight = row["morning_weight"] if row else None
    is_closed = bool(row["is_closed"]) if row else False

    nav1, nav2, _ = st.columns([1, 1, 3])
    with nav1:
        if st.button("⬅️ Giorno precedente"):
            goto_day(d - timedelta(days=1))
    with nav2:
        if st.button("Giorno successivo ➡️"):
            goto_day(d + timedelta(days=1))

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modificare.")
        if st.button("🔓 Riapri giornata"):
            upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    # --------------------
    # PREVISTO
    # --------------------
    st.subheader("🗓️ Previsto (pianificato)")
    planned = planned_for_day(user_id, d)

    add_col1, add_col2, add_col3, add_col4 = st.columns([1, 1, 2, 2])
    with add_col1:
        p_type = st.selectbox(
            "Tipo",
            ["meal", "workout"],
            format_func=lambda x: "Pasto" if x == "meal" else "Allenamento",
            key=f"ptype_{ds}",
            disabled=is_closed
        )
    with add_col2:
        p_time = st.text_input("Ora", value="08:00", key=f"ptime_{ds}", disabled=is_closed)
    with add_col3:
        p_title = st.text_input("Titolo", value="", key=f"ptitle_{ds}", disabled=is_closed)
    with add_col4:
        p_notes = st.text_input("Note", value="", key=f"pnotes_{ds}", disabled=is_closed)

    cA, cB, cC = st.columns([1, 1, 2])
    with cA:
        p_kcal = st.number_input(
            "Kcal previste", min_value=0, value=0, step=50, key=f"pkcal_{ds}", disabled=is_closed
        )
    with cB:
        p_dur = st.number_input(
            "Durata (min) (solo workout)", min_value=0, value=0, step=5, key=f"pdur_{ds}", disabled=is_closed
        )
    with cC:
        if st.button("➕ Aggiungi al previsto", disabled=is_closed, key=f"addplanned_{ds}"):
            if not p_title.strip():
                st.error("Inserisci un titolo.")
            else:
                add_planned_event(
                    user_id, d,
                    time_str=p_time.strip(),
                    typ=p_type,
                    title=p_title.strip(),
                    expected_calories=float(p_kcal) if p_kcal > 0 else None,
                    duration_min=int(p_dur) if (p_type == "workout" and p_dur > 0) else None,
                    notes=p_notes.strip() if p_notes.strip() else None
                )
                st.rerun()

    if planned.empty:
        st.caption("Nessun evento pianificato per questo giorno.")
    else:
        for _, r in planned.iterrows():
            left, mid, right = st.columns([6, 2, 2])
            tag = "🍽️" if r["type"] == "meal" else "🏃"
            kcal = f"~{kcal_round(r['expected_calories'])} kcal" if pd.notna(r["expected_calories"]) else ""
            dur = f"{int(r['duration_min'])} min" if pd.notna(r["duration_min"]) else ""
            status = r["status"] or "planned"

            with left:
                st.markdown(f"**{tag} {r['time']} — {r['title']}**  \n{kcal} {dur}  \n`{status}`")
                if r["notes"]:
                    st.caption(r["notes"])
            with mid:
                done = st.checkbox(
                    "Fatto", value=(status == "done"),
                    key=f"done_{ds}_{int(r['id'])}", disabled=is_closed
                )
                if done and status != "done" and not is_closed:
                    mark_planned_done_to_actual(user_id, d, r.to_dict())
                    st.rerun()
            with right:
                if st.button("🗑️", key=f"delplanned_{ds}_{int(r['id'])}", disabled=is_closed):
                    delete_planned_event(user_id, int(r["id"]))
                    st.rerun()

    # --------------------
    # ✅ PASTO: TESTO / FOTO (stima + salva)
    # --------------------
    st.divider()
    st.subheader("🍽️ Registra pasto (stima calorie)")

    tab_txt, tab_img = st.tabs(["✍️ Da testo", "📷 Da foto"])

    with tab_txt:
        meal_time = st.text_input("Ora pasto", value="13:00", key=f"meal_time_txt_{ds}", disabled=is_closed)
        meal_text = st.text_area("Descrivi il pasto", key=f"meal_desc_{ds}", height=110, disabled=is_closed)
        if st.button("Stima e salva pasto", key=f"meal_est_save_{ds}", disabled=is_closed):
            if not (meal_text or "").strip():
                st.error("Scrivi una descrizione del pasto.")
            else:
                data = estimate_meal_from_text(meal_text)
                kcal = float(data.get("total_calories") or 0)
                desc = str(data.get("description") or meal_text or "Pasto")
                conn.execute(
                    "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                    (user_id, ds, meal_time, desc, kcal, str(data))
                )
                conn.commit()
                st.success(f"Salvato: {int(round(kcal))} kcal")
                st.rerun()

    with tab_img:
        meal_time2 = st.text_input("Ora pasto", value="20:30", key=f"meal_time_img_{ds}", disabled=is_closed)
        note = st.text_input("Nota (opzionale)", key=f"meal_note_{ds}", disabled=is_closed)
        up = st.file_uploader(
            "Carica foto del pasto",
            type=["png", "jpg", "jpeg"],
            key=f"meal_photo_{ds}",
            disabled=is_closed
        )
        if st.button("Analizza foto e salva", key=f"meal_photo_save_{ds}", disabled=is_closed):
            if not up:
                st.error("Carica una foto.")
            else:
                data = analyze_food_photo(up.getvalue(), up.type, meal_time2, note)
                kcal = float(data.get("total_calories") or 0)
                desc = str(data.get("description") or "Pasto (foto)")
                conn.execute(
                    "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                    (user_id, ds, meal_time2, desc, kcal, str(data))
                )
                conn.commit()
                st.success(f"Salvato: {int(round(kcal))} kcal")
                st.rerun()

    # --------------------
    # (OPZIONALE) Mostra pasti salvati del giorno
    # --------------------
    st.divider()
    st.subheader("📌 Pasti registrati (oggi)")

    meals = safe_read_sql(
        "SELECT id, time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    if meals.empty:
        st.caption("Nessun pasto registrato per questo giorno.")
    else:
        for _, r in meals.iterrows():
            c1, c2 = st.columns([8, 2])
            with c1:
                st.markdown(f"**{r['time']}** — {r['description']}")
                st.caption(f"{kcal_round(r['calories'])} kcal")
            with c2:
                if st.button("🗑️", key=f"delmeal_{ds}_{int(r['id'])}", disabled=is_closed):
                    conn.execute("DELETE FROM meals WHERE user_id=? AND id=?", (user_id, int(r["id"])))
                    conn.commit()
                    st.rerun()


# ----------------------------
# Weekly plan (INVARIATO)
# ----------------------------
def build_weekly_plan_prompt(profile: dict, week_start: date, workout_slots: pd.DataFrame, last_week_sums: pd.DataFrame) -> str:
    lines = []
    lines.append("Sei un coach nutrizionale/fitness. Crea un piano settimanale pratico e sostenibile.")
    lines.append("")
    lines.append("VINCOLI IMPORTANTI:")
    lines.append("- Distribuisci i pasti su ogni giorno con orari (colazione, pranzo, cena + eventuali spuntini).")
    lines.append("- Coerenza con obiettivo e data obiettivo.")
    lines.append("- Inserisci kcal stimate per ogni pasto e un totale giornaliero stimato.")
    lines.append("- Non cambiare i giorni/orari delle sedute allenamento scelte dall'utente.")
    lines.append("")
    lines.append(f"SETTIMANA START (lunedì): {week_start}")
    lines.append("")
    lines.append("PROFILO UTENTE:")
    for k in ["start_weight", "height_cm", "sex", "age", "activity_level", "goal_type", "goal_weight", "goal_date", "body_fat", "lean_mass"]:
        lines.append(f"- {k}: {profile.get(k)}")

    lines.append("")
    lines.append("ALLENAMENTI PREVISTI (GIORNO/ORA/DURATA):")
    if workout_slots is not None and not workout_slots.empty:
        for _, r in workout_slots.iterrows():
            lines.append(f"- {r.get('date')} {r.get('time')} — {r.get('title')} ({int(r.get('duration_min') or 0)} min)")
    else:
        lines.append("- nessuno")

    lines.append("")
    lines.append("ULTIMA SETTIMANA (se presente) - riepilogo:")
    if last_week_sums is not None and not last_week_sums.empty:
        lines.append(f"- giorni: {len(last_week_sums)}")
        lines.append(f"- media IN: {last_week_sums['calories_in'].mean():.0f}")
        lines.append(f"- media OUT: {last_week_sums['calories_out'].mean():.0f}")
        lines.append(f"- media NET: {last_week_sums['net_calories'].mean():.0f}")
    else:
        lines.append("- nessun dato")

    lines.append("")
    lines.append("OUTPUT:")
    lines.append("Scrivi un piano giorno-per-giorno (Lun→Dom), con:")
    lines.append("- orario + nome pasto + descrizione breve + kcal stimate")
    lines.append("- allenamento (se previsto) con orario")
    lines.append("- totale kcal giornaliero stimato")
    lines.append("")
    lines.append("ORARI CONSIGLIATI:")
    lines.append("- 08:00 colazione")
    lines.append("- 13:00 pranzo")
    lines.append("- 17:00 spuntino")
    lines.append("- 20:30 cena")
    return "\n".join(lines)


def _daily_target_kcal(profile: dict, rest_kcal: float) -> float:
    goal_type = str(profile.get("goal_type") or "mantenimento").lower()
    if "dimagr" in goal_type or "deficit" in goal_type:
        return max(rest_kcal - 500, 1200)
    if "massa" in goal_type or "surplus" in goal_type:
        return rest_kcal + 250
    return rest_kcal


def _apply_plan_to_calendar(user_id: int, week_start: date, plan_text: str, workout_slots: pd.DataFrame):
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

    conn.execute(
        "DELETE FROM planned_events WHERE user_id=? AND date>=? AND date<=?",
        (user_id, str(week_start), str(week_end))
    )
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

    if workout_slots is not None and not workout_slots.empty:
        for _, r in workout_slots.iterrows():
            ds = str(r.get("date"))
            time_str = str(r.get("time") or "19:00")
            title = str(r.get("title") or "Allenamento")
            dur = int(r.get("duration_min") or 0)

            try:
                d0 = date.fromisoformat(ds)
            except Exception:
                continue
            if d0 < week_start or d0 > week_end:
                continue

            kcal_burn = float(heuristic_workout_kcal(title, dur))

            conn.execute(
                """
                INSERT INTO planned_events
                  (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (user_id, ds, time_str, "workout", title, kcal_burn,
                 int(dur) if dur > 0 else None, "planned", "Allenamento pianificato")
            )

    conn.commit()


def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale → Inserisci nel calendario (previsto)")

    today = date.today()
    default_start = today + timedelta(days=(7 - today.weekday()) % 7)  # prossimo lunedì
    week_start = st.date_input("Settimana da pianificare (lunedì)", value=default_start)

    st.subheader("Allenamenti previsti (scegli tu giorni e orari)")
    if "workout_slots" not in st.session_state:
        st.session_state.workout_slots = pd.DataFrame(
            [
                {"date": str(week_start), "time": "19:00", "title": "Pesi", "duration_min": 60},
                {"date": str(week_start + timedelta(days=2)), "time": "19:00", "title": "Cardio", "duration_min": 40},
            ]
        )

    edited = st.data_editor(
        st.session_state.workout_slots,
        use_container_width=True,
        num_rows="dynamic",
        key="workout_slots_editor"
    )
    st.session_state.workout_slots = edited

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
        colx, coly = st.columns(2)
        with colx:
            if st.button("Re-inserisci eventi nel calendario (previsto)"):
                _apply_plan_to_calendar(user_id, week_start, existing["content"], st.session_state.workout_slots)
                st.success("Eventi previsti inseriti nel calendario ✅")
        with coly:
            if st.button("Rigenera piano (nuova chiamata)"):
                existing = None

    if not existing:
        if st.button("🔄 Genera piano + Inserisci nel calendario"):
            prompt = build_weekly_plan_prompt(
                profile=prof,
                week_start=week_start,
                workout_slots=st.session_state.workout_slots,
                last_week_sums=last_week_sums
            )
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