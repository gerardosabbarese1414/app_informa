import streamlit as st
import pandas as pd
import plotly.express as px
import calendar as cal
from datetime import date, datetime, timedelta

from database import conn
from profile import get_profile
from utils import bmr_mifflin, tdee_from_level, iso_year_week, kcal_round
from ai import (
    analyze_food_photo,
    estimate_meal_from_text,
    estimate_workout_from_text,
    generate_weekly_plan,
    explain_openai_error,
)


# ----------------------------
# Helpers
# ----------------------------
def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()


def set_active_page(name: str):
    st.session_state.page = name


def upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    ds = str(d)
    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    if row:
        mw = morning_weight if morning_weight is not None else row[0]
        ic = int(is_closed) if is_closed is not None else row[1]
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
        "SELECT COUNT(*) FROM planned_events WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()[0]

    return {
        "weight": day[0] if day else None,
        "closed": bool(day[1]) if day else False,
        "in": summ[0] if summ else None,
        "out": summ[1] if summ else None,
        "net": summ[2] if summ else None,
        "planned": planned_count,
    }


# ----------------------------
# Planned events (previsto)
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
    """
    Converte un evento previsto in un evento reale:
    - meal -> inserisce in meals
    - workout -> inserisce in workouts
    """
    ds = str(d)
    typ = planned_row.get("type")

    if typ == "meal":
        conn.execute(
            "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
            (
                user_id,
                ds,
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
                user_id,
                ds,
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
# Pages
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


def month_calendar_page(user_id: int):
    st.header("📅 Calendario (mese)")

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    c1, c2 = st.columns(2)
    with c1:
        year = st.number_input("Anno", 2020, 2100, st.session_state.selected_date.year, 1)
    with c2:
        month = st.number_input("Mese", 1, 12, st.session_state.selected_date.month, 1)

    month_matrix = cal.monthcalendar(int(year), int(month))
    st.caption("Click su un giorno → vai alla compilazione (Giornata).")

    headers = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    hcols = st.columns(7)
    for i, h in enumerate(headers):
        hcols[i].markdown(f"**{h}**")

    for week in month_matrix:
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            if day_num == 0:
                cols[i].markdown(" ")
                continue

            d = date(int(year), int(month), int(day_num))
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

            # Preview planned: prendiamo max 2 eventi per giorno
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

            # Button giorno: porta alla pagina “Giornata”
            if cols[i].button(f"{day_num}", key=f"day_{year}_{month}_{day_num}", use_container_width=True):
                st.session_state.selected_date = d
                set_active_page("Giornata")
                st.rerun()

            preview = f"{badge} **{day_num}**"
            if p["weight"] is not None:
                preview += f"\n{p['weight']:.1f} kg"
            if p["net"] is not None:
                preview += f"\n<span class='{color_cls}'>NET {kcal_round(p['net'])}</span>"

            # Eventi pianificati sotto
            if p["planned"] > 0:
                preview += f"\n🗓️ {p['planned']} prev."
            cols[i].markdown(preview, unsafe_allow_html=True)

            # mini lista eventi
            if not planned_preview.empty:
                lines = []
                for _, r in planned_preview.iterrows():
                    tag = "🍽️" if r["type"] == "meal" else "🏃"
                    kcal = f"~{kcal_round(r['expected_calories'])}kcal" if r["expected_calories"] is not None else ""
                    lines.append(f"{tag} {r['time']} {kcal}")
                cols[i].caption("\n".join(lines))


def day_page(user_id: int, d: date):
    ds = str(d)
    st.header(f"🗓️ Giornata: {ds}")

    # --- stato giorno ---
    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    morning_weight = row[0] if row else None
    is_closed = bool(row[1]) if row else False

    # Pulsanti navigazione rapida
    nav1, nav2, nav3 = st.columns([1, 1, 3])
    with nav1:
        if st.button("⬅️ Giorno precedente"):
            st.session_state.selected_date = d - timedelta(days=1)
            st.rerun()
    with nav2:
        if st.button("Giorno successivo ➡️"):
            st.session_state.selected_date = d + timedelta(days=1)
            st.rerun()

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modificare.")
        if st.button("🔓 Riapri giornata"):
            upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    # ----------------------------
    # PREVISTO (planned)
    # ----------------------------
    st.subheader("🗓️ Previsto (pianificato)")
    planned = planned_for_day(user_id, d)

    add_col1, add_col2, add_col3, add_col4 = st.columns([1, 1, 2, 2])
    with add_col1:
        p_type = st.selectbox("Tipo", ["meal", "workout"], format_func=lambda x: "Pasto" if x == "meal" else "Allenamento",
                              key=f"ptype_{ds}", disabled=is_closed)
    with add_col2:
        p_time = st.text_input("Ora", value="08:00", key=f"ptime_{ds}", disabled=is_closed)
    with add_col3:
        p_title = st.text_input("Titolo", value="", key=f"ptitle_{ds}", disabled=is_closed)
    with add_col4:
        p_notes = st.text_input("Note", value="", key=f"pnotes_{ds}", disabled=is_closed)

    cA, cB, cC = st.columns([1, 1, 2])
    with cA:
        p_kcal = st.number_input("Kcal previste", min_value=0, value=0, step=50, key=f"pkcal_{ds}", disabled=is_closed)
    with cB:
        p_dur = st.number_input("Durata (min) (solo workout)", min_value=0, value=0, step=5, key=f"pdur_{ds}", disabled=is_closed)
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
        st.caption("Nessun evento pianificato per questo giorno (aggiungilo sopra o dal piano settimanale).")
    else:
        # Rendering con checkbox “fatto” e azioni
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
                done = st.checkbox("Fatto", value=(status == "done"), key=f"done_{ds}_{int(r['id'])}", disabled=is_closed)
                if done and status != "done" and not is_closed:
                    mark_planned_done_to_actual(user_id, d, r.to_dict())
                    st.rerun()

            with right:
                if st.button("🗑️", key=f"delplanned_{ds}_{int(r['id'])}", disabled=is_closed):
                    delete_planned_event(user_id, int(r["id"]))
                    st.rerun()

    st.divider()

    # ----------------------------
    # REALE (actual): peso/pasti/allenamenti
    # ----------------------------
    st.subheader("✅ Reale (effettivo)")

    # Peso mattina
    st.markdown("### ⚖️ Peso mattina")
    w = st.number_input(
        "Peso (kg)",
        value=float(morning_weight) if morning_weight is not None else 0.0,
        step=0.1,
        disabled=is_closed,
        key=f"w_{ds}"
    )
    if st.button("Salva peso", disabled=is_closed, key=f"savew_{ds}"):
        upsert_day_log(user_id, d, morning_weight=w, is_closed=0)
        st.success("Peso salvato ✅")

    # Pasti reali
    st.markdown("### 🍽️ Pasti (reali)")

    # Foto
    st.markdown("#### 📷 Da foto")
    f1, f2 = st.columns([1, 2])
    with f1:
        photo_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"pt_real_{ds}", disabled=is_closed)
    with f2:
        photo_note = st.text_input("Nota", key=f"pn_real_{ds}", disabled=is_closed)
    up = st.file_uploader("Carica foto", type=["jpg", "jpeg", "png"], disabled=is_closed, key=f"up_real_{ds}")

    if up and not is_closed:
        if st.button("🔎 Stima da foto", key=f"an_photo_real_{ds}"):
            with st.spinner("Analizzo foto..."):
                try:
                    st.session_state[f"photo_res_real_{ds}"] = analyze_food_photo(
                        up.getvalue(), up.type or "image/jpeg", photo_time, photo_note or ""
                    )
                except Exception as e:
                    st.error(explain_openai_error(e))

        res = st.session_state.get(f"photo_res_real_{ds}")
        if res and "total_calories" in res:
            st.success(f"Stima: {kcal_round(res.get('total_calories'))} kcal")
            if st.button("✅ Aggiungi pasto (foto)", key=f"add_photo_real_{ds}", disabled=is_closed):
                desc = res.get("description", "Pasto (foto)")
                if photo_note:
                    desc = f"{desc} — Nota: {photo_note}"
                conn.execute(
                    "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                    (user_id, ds, photo_time, desc, float(res.get("total_calories") or 0), str(res))
                )
                conn.commit()
                st.session_state.pop(f"photo_res_real_{ds}", None)
                st.rerun()

    # Manuale
    st.markdown("#### ✍️ Manuale")
    m1, m2, m3 = st.columns([1, 2, 1])
    with m1:
        meal_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"mt_real_{ds}", disabled=is_closed)
    with m2:
        meal_text = st.text_input("Cosa hai mangiato", key=f"mtext_real_{ds}", disabled=is_closed)
    with m3:
        meal_kcal = st.number_input("Kcal (opz.)", min_value=0, value=0, step=50, key=f"mk_real_{ds}", disabled=is_closed)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🤖 Stima con AI", key=f"est_meal_real_{ds}", disabled=is_closed):
            try:
                st.session_state[f"meal_ai_real_{ds}"] = estimate_meal_from_text(meal_text)
            except Exception as e:
                st.error(explain_openai_error(e))

    ai_meal = st.session_state.get(f"meal_ai_real_{ds}")
    if ai_meal and "total_calories" in ai_meal:
        st.info(f"AI: {kcal_round(ai_meal.get('total_calories'))} kcal — {ai_meal.get('notes','')}")

    with c2:
        if st.button("➕ Aggiungi pasto", key=f"add_meal_real_{ds}", disabled=is_closed):
            if not meal_text.strip():
                st.error("Inserisci una descrizione del pasto.")
            else:
                kcal_value = float(meal_kcal)
                raw = None
                if kcal_value == 0 and ai_meal and "total_calories" in ai_meal:
                    kcal_value = float(ai_meal.get("total_calories") or 0)
                    raw = str(ai_meal)
                conn.execute(
                    "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                    (user_id, ds, meal_time, meal_text.strip(), kcal_value, raw)
                )
                conn.commit()
                st.session_state.pop(f"meal_ai_real_{ds}", None)
                st.rerun()

    meals = safe_read_sql(
        "SELECT id, time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    total_in = float(meals["calories"].fillna(0).sum()) if not meals.empty else 0.0
    if not meals.empty:
        st.dataframe(meals.drop(columns=["id"]), use_container_width=True)
        del_id = st.number_input("ID pasto da eliminare", min_value=0, value=0, step=1, key=f"delmeal_{ds}", disabled=is_closed)
        if st.button("🗑️ Elimina pasto", key=f"delmealbtn_{ds}", disabled=is_closed):
            if del_id > 0:
                conn.execute("DELETE FROM meals WHERE user_id=? AND id=?", (user_id, int(del_id)))
                conn.commit()
                st.rerun()
    st.metric("Totale calorie ingerite", f"{kcal_round(total_in)} kcal")

    # Allenamenti reali
    st.markdown("### 🏃 Allenamento (reale)")
    w1, w2 = st.columns([1, 2])
    with w1:
        wo_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"wt_real_{ds}", disabled=is_closed)
        duration = st.number_input("Durata (min)", min_value=0, value=0, step=5, key=f"wd_real_{ds}", disabled=is_closed)
    with w2:
        wo_text = st.text_input("Descrizione", key=f"wtext_real_{ds}", disabled=is_closed)
        wo_kcal = st.number_input("Kcal bruciate (opz.)", min_value=0, value=0, step=25, key=f"wk_real_{ds}", disabled=is_closed)

    prof = get_profile(user_id) or {}
    weight_for_calc = (w if w > 0 else (morning_weight or prof.get("start_weight") or 75.0))
    height_for_calc = (prof.get("height_cm") or 175.0)

    c3, c4 = st.columns(2)
    with c3:
        if st.button("🤖 Stima allenamento con AI", key=f"est_wo_real_{ds}", disabled=is_closed):
            try:
                st.session_state[f"wo_ai_real_{ds}"] = estimate_workout_from_text(
                    f"{wo_text} per {int(duration)} minuti",
                    float(weight_for_calc) if weight_for_calc else None,
                    float(height_for_calc) if height_for_calc else None
                )
            except Exception as e:
                st.error(explain_openai_error(e))

    ai_wo = st.session_state.get(f"wo_ai_real_{ds}")
    if ai_wo and "calories_burned" in ai_wo:
        st.info(f"AI: {kcal_round(ai_wo.get('calories_burned'))} kcal — {ai_wo.get('notes','')}")

    with c4:
        if st.button("➕ Aggiungi allenamento", key=f"add_wo_real_{ds}", disabled=is_closed):
            if not wo_text.strip() or duration <= 0:
                st.error("Inserisci descrizione e durata.")
            else:
                kcal_burn = float(wo_kcal)
                raw = None
                if kcal_burn == 0 and ai_wo and "calories_burned" in ai_wo:
                    kcal_burn = float(ai_wo.get("calories_burned") or 0)
                    raw = str(ai_wo)
                conn.execute(
                    """
                    INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (user_id, ds, wo_time, wo_text.strip(), int(duration), kcal_burn, raw)
                )
                conn.commit()
                st.session_state.pop(f"wo_ai_real_{ds}", None)
                st.rerun()

    workouts = safe_read_sql(
        "SELECT id, time, description, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    total_workout = float(workouts["calories_burned"].fillna(0).sum()) if not workouts.empty else 0.0
    if not workouts.empty:
        st.dataframe(workouts.drop(columns=["id"]), use_container_width=True)
        delw_id = st.number_input("ID allenamento da eliminare", min_value=0, value=0, step=1, key=f"delwo_{ds}", disabled=is_closed)
        if st.button("🗑️ Elimina allenamento", key=f"delwobtn_{ds}", disabled=is_closed):
            if delw_id > 0:
                conn.execute("DELETE FROM workouts WHERE user_id=? AND id=?", (user_id, int(delw_id)))
                conn.commit()
                st.rerun()
    st.metric("Totale calorie bruciate (allenamento)", f"{kcal_round(total_workout)} kcal")

    # TDEE matematico
    st.markdown("### 🔥 Calorie a riposo (TDEE stimato)")
    sex = prof.get("sex") or "M"
    age = int(prof.get("age") or 25)
    height_cm = float(prof.get("height_cm") or 175.0)
    act = (prof.get("activity_level") or "leggero").lower()
    bmr = bmr_mifflin(sex, float(weight_for_calc), height_cm, age)
    rest = tdee_from_level(bmr, act)
    st.write(f"TDEE stimato: **{kcal_round(rest)} kcal/giorno**")

    # Chiudi giornata
    st.divider()
    st.subheader("🔒 Chiudi giornata (salva riepilogo)")
    calories_out = float(rest) + float(total_workout)
    net = float(total_in) - calories_out
    st.write(
        f"IN **{kcal_round(total_in)}** — OUT **{kcal_round(calories_out)}** "
        f"(rest {kcal_round(rest)} + wo {kcal_round(total_workout)}) — NET **{kcal_round(net)}**"
    )

    if st.button("🔒 Chiudi giornata", disabled=is_closed, key=f"close_{ds}"):
        upsert_day_log(user_id, d, morning_weight=(w if w > 0 else morning_weight), is_closed=1)
        conn.execute(
            """
            REPLACE INTO daily_summaries
              (user_id, date, calories_in, rest_calories, workout_calories, calories_out, net_calories)
            VALUES (?,?,?,?,?,?,?)
            """,
            (user_id, ds, float(total_in), float(rest), float(total_workout), float(calories_out), float(net))
        )
        conn.commit()
        st.success("Giornata chiusa ✅")
        st.rerun()


def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale → Inserisci nel calendario (previsto)")

    today = date.today()
    # week_start: prossimo lunedì come default
    default_start = today + timedelta(days=(7 - today.weekday()) % 7)
    week_start = st.date_input("Settimana da pianificare (lunedì)", value=default_start)

    st.subheader("Allenamenti previsti (scegli tu giorni e orari)")
    # tabellina editabile
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

    # Recupera settimana precedente per contesto
    prev_start = week_start - timedelta(days=7)
    prev_end = week_start - timedelta(days=1)
    last_week_sums = safe_read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date>=? AND date<=? ORDER BY date",
        (user_id, str(prev_start), str(prev_end))
    )

    # Se già generato, mostralo (cache in weekly_plan) per quella settimana
    y, w = iso_year_week(week_start)
    existing = conn.execute(
        "SELECT content, created_at FROM weekly_plan WHERE user_id=? AND iso_year=? AND iso_week=?",
        (user_id, y, w)
    ).fetchone()

    if existing:
        st.caption(f"Piano già generato (cache) — {existing[1]}")
        st.markdown(existing[0])
        colx, coly = st.columns(2)
        with colx:
            if st.button("Re-inserisci eventi nel calendario (previsto)"):
                _apply_plan_text_to_calendar(user_id, week_start, existing[0], st.session_state.workout_slots)
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
                "REPLACE INTO weekly_plan (user_id, iso_year, iso_week, content, created_at) VALUES (?,?,?,?,?)",
                (user_id, y, w, content, datetime.now().isoformat(timespec="seconds"))
            )
            conn.commit()

            _apply_plan_text_to_calendar(user_id, week_start, content, st.session_state.workout_slots)
            st.success("Piano generato e inserito nel calendario ✅")
            st.rerun()


def build_weekly_plan_prompt(profile: dict, week_start: date, workout_slots: pd.DataFrame, last_week_sums: pd.DataFrame) -> str:
    # Prompt “ibrido”: numeri e vincoli tuoi, GPT produce piano leggibile + struttura
    # (per ora testo; nel prossimo step lo trasformiamo in JSON strutturato)
    lines = []
    lines.append("Sei un coach nutrizionale/fitness. Crea un piano settimanale pratico.")
    lines.append("")
    lines.append("VINCOLI IMPORTANTI:")
    lines.append("- Deve distribuire i pasti su ogni giorno con orari (colazione, pranzo, cena + eventuali spuntini).")
    lines.append("- Deve essere coerente con l'obiettivo e la data obiettivo.")
    lines.append("- Inserisci kcal stimate per ogni pasto e un totale giornaliero stimato.")
    lines.append("- Non cambiare i giorni/orari delle sedute allenamento scelte dall'utente: puoi solo migliorare contenuti e suggerimenti.")
    lines.append("")
    lines.append(f"SETTIMANA START (lunedì): {week_start}")
    lines.append("")
    lines.append("PROFILO UTENTE:")
    for k in ["start_weight", "height_cm", "sex", "age", "activity_level", "goal_type", "goal_weight", "goal_date"]:
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
    lines.append("ORARI CONSIGLIATI (usa questi se non hai motivi per cambiarli):")
    lines.append("- 08:00 colazione")
    lines.append("- 13:00 pranzo")
    lines.append("- 17:00 spuntino")
    lines.append("- 20:30 cena")
    return "\n".join(lines)


def _estimate_workout_kcal(title: str, duration_min: int) -> float:
    """
    Stima stabile (no GPT) per kcal bruciate (kcal/min).
    """
    t = (title or "").lower()
    dur = max(int(duration_min or 0), 0)

    if "corsa" in t or "run" in t:
        kpm = 10.0
    elif "pesi" in t or "forza" in t or "gym" in t:
        kpm = 6.0
    elif "cammin" in t or "walk" in t:
        kpm = 5.0
    elif "bike" in t or "cicl" in t:
        kpm = 8.0
    else:
        kpm = 7.5

    return float(kpm * dur)


def _daily_target_kcal(profile: dict, rest_kcal: float) -> float:
    """
    Target giornaliero basato su goal (semplice e robusto).
    """
    goal_type = (profile.get("goal_type") or "mantenimento").lower()

    if "dimagr" in goal_type or "deficit" in goal_type:
        return max(rest_kcal - 500, 1200)
    if "massa" in goal_type or "surplus" in goal_type:
        return rest_kcal + 250
    return rest_kcal


def _apply_plan_text_to_calendar(user_id: int, week_start: date, plan_text: str, workout_slots: pd.DataFrame):
    """
    Inserisce nel calendario (planned_events) eventi pianificati per la settimana.
    Non fa parsing del testo (troppo fragile): crea eventi coerenti e calcolati.
    """
    prof = get_profile(user_id) or {}

    # parametri base per TDEE
    weight = float(prof.get("start_weight") or 75.0)
    height = float(prof.get("height_cm") or 175.0)
    sex = (prof.get("sex") or "M")
    age = int(prof.get("age") or 25)
    act = (prof.get("activity_level") or "leggero").lower()

    bmr = bmr_mifflin(sex, weight, height, age)
    rest = tdee_from_level(bmr, act)
    target_in = _daily_target_kcal(prof, rest)

    # ripartizione pasti
    meal_slots = [
        ("08:00", "Colazione (piano)", 0.25),
        ("13:00", "Pranzo (piano)", 0.35),
        ("17:00", "Spuntino (piano)", 0.10),
        ("20:30", "Cena (piano)", 0.30),
    ]

    week_end = week_start + timedelta(days=6)

    # pulisci planned della settimana (se rigeneri)
    conn.execute(
        "DELETE FROM planned_events WHERE user_id=? AND date>=? AND date<=?",
        (user_id, str(week_start), str(week_end))
    )
    conn.commit()

    # nota breve dal piano testuale
    note = (plan_text or "").strip()
    if len(note) > 350:
        note = note[:350] + "…"

    # inserisci pasti
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

    # inserisci allenamenti scelti dall’utente
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

            kcal_burn = _estimate_workout_kcal(title, dur)

            conn.execute(
                """
                INSERT INTO planned_events
                  (user_id, date, time, type, title, expected_calories, duration_min, status, notes)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (user_id, ds, time_str, "workout", title, float(kcal_burn),
                 int(dur) if dur > 0 else None, "planned", "Allenamento pianificato")
            )

    conn.commit()