import streamlit as st
import pandas as pd
import plotly.express as px
import calendar as cal
from datetime import date, timedelta

from database import conn
from profile import get_profile
from utils import bmr_mifflin, tdee_from_level, kcal_round
from ai import analyze_food_photo, estimate_meal_from_text, estimate_workout_from_text


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
# Daily summary recompute (IN/OUT/NET)
# ----------------------------
def recompute_daily_summary(user_id: int, d: date):
    ds = str(d)

    meals = conn.execute(
        "SELECT COALESCE(SUM(calories),0) AS s FROM meals WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()["s"]

    workouts = conn.execute(
        "SELECT COALESCE(SUM(calories_burned),0) AS s FROM workouts WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()["s"]

    prof = get_profile(user_id) or {}
    weight = float((prof.get("start_weight") or 75.0))
    height = float((prof.get("height_cm") or 175.0))
    sex = str((prof.get("sex") or "M"))
    age = int((prof.get("age") or 25))
    act = str((prof.get("activity_level") or "leggero")).lower()

    bmr = bmr_mifflin(sex, weight, height, age)
    rest = float(tdee_from_level(bmr, act))

    calories_in = float(meals or 0)
    rest_calories = float(rest)
    workout_calories = float(workouts or 0)
    calories_out = rest_calories + workout_calories
    net = calories_in - calories_out

    conn.execute(
        """
        INSERT INTO daily_summaries (user_id, date, calories_in, rest_calories, workout_calories, calories_out, net_calories)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(user_id, date) DO UPDATE SET
          calories_in=excluded.calories_in,
          rest_calories=excluded.rest_calories,
          workout_calories=excluded.workout_calories,
          calories_out=excluded.calories_out,
          net_calories=excluded.net_calories
        """,
        (user_id, ds, calories_in, rest_calories, workout_calories, calories_out, net)
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
# Calendario mese (CARD BUTTON)
# ----------------------------
def month_calendar_page(user_id: int):
    st.header("📅 Calendario (mese)")
    st.caption("Clicca un giorno → apre la Giornata (senza reset della sessione).")

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        year = int(st.number_input("Anno", 2020, 2100, st.session_state.selected_date.year, 1, key="cal_year"))
    with c2:
        month = int(st.number_input("Mese", 1, 12, st.session_state.selected_date.month, 1, key="cal_month"))
    with c3:
        if st.button("📍 Vai a oggi", key="cal_today"):
            st.session_state.selected_date = date.today()
            st.rerun()

    headers = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
    hcols = st.columns(7)
    for i, h in enumerate(headers):
        hcols[i].markdown(f"**{h}**")

    month_matrix = cal.monthcalendar(year, month)  # Monday-first
    today = date.today()

    # scope CSS solo qui
    st.markdown("<div class='cal-grid-scope'>", unsafe_allow_html=True)

    for week in month_matrix:
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            with cols[i]:
                if day_num == 0:
                    st.button(" ", disabled=True, key=f"empty_{year}_{month}_{i}_{len(month_matrix)}", use_container_width=True)
                    continue

                d = date(year, month, int(day_num))
                p = fetch_day_preview(user_id, d)

                badge = "✅" if p["closed"] else "•"

                color_txt = ""
                if p["net"] is not None:
                    if p["net"] <= 0:
                        color_txt = "OK"
                    elif p["net"] <= 300:
                        color_txt = "ATT"
                    else:
                        color_txt = "HIGH"

                meta = []
                if p["weight"] is not None:
                    meta.append(f"{float(p['weight']):.1f} kg")
                if p["net"] is not None:
                    meta.append(f"NET {kcal_round(p['net'])} ({color_txt})")
                if p["planned"] > 0:
                    meta.append(f"🗓️ {p['planned']}")

                star = "⭐ " if d == today else ""
                label = f"{star}{day_num} {badge}\n" + ("\n".join(meta) if meta else "")

                if st.button(label, key=f"day_{d.isoformat()}", use_container_width=True):
                    goto_day(d)

    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# Giornata
# ----------------------------
def day_page(user_id: int, d: date):
    ds = str(d)
    st.header(f"🗓️ Giornata: {ds}")

    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()
    morning_weight = float(row["morning_weight"]) if row and row["morning_weight"] is not None else None
    is_closed = bool(row["is_closed"]) if row else False

    nav1, nav2, nav3 = st.columns([1, 1, 3])
    with nav1:
        if st.button("⬅️ Giorno precedente", key=f"prev_{ds}"):
            goto_day(d - timedelta(days=1))
    with nav2:
        if st.button("Giorno successivo ➡️", key=f"next_{ds}"):
            goto_day(d + timedelta(days=1))
    with nav3:
        if st.button("⬅️ Torna al Calendario", key=f"back_cal_{ds}"):
            st.session_state.page = "Calendario"
            st.rerun()

    # Peso + chiusura
    st.subheader("⚖️ Peso e stato giornata")
    c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
    with c1:
        w = st.number_input("Peso (kg)", min_value=0.0, value=float(morning_weight or 0.0), step=0.1, key=f"w_{ds}", disabled=is_closed)
    with c2:
        if st.button("💾 Salva peso", key=f"save_w_{ds}", disabled=is_closed):
            upsert_day_log(user_id, d, morning_weight=float(w) if w > 0 else None)
            recompute_daily_summary(user_id, d)
            st.rerun()
    with c3:
        if is_closed:
            if st.button("🔓 Riapri", key=f"reopen_{ds}"):
                upsert_day_log(user_id, d, is_closed=0)
                st.rerun()
        else:
            if st.button("✅ Chiudi giornata", key=f"close_{ds}"):
                recompute_daily_summary(user_id, d)
                upsert_day_log(user_id, d, is_closed=1)
                st.rerun()
    with c4:
        summ = conn.execute(
            "SELECT calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date=?",
            (user_id, ds)
        ).fetchone()
        if summ:
            st.markdown(
                f"**IN:** {kcal_round(summ['calories_in'])}  |  **OUT:** {kcal_round(summ['calories_out'])}  |  **NET:** {kcal_round(summ['net_calories'])}"
            )
        else:
            st.caption("Nessun riepilogo ancora.")

    # PASTI
    st.divider()
    st.subheader("🍽️ Pasti (stima calorie)")
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
                recompute_daily_summary(user_id, d)
                st.rerun()

    with tab_img:
        meal_time2 = st.text_input("Ora pasto", value="20:30", key=f"meal_time_img_{ds}", disabled=is_closed)
        note = st.text_input("Nota (opzionale)", key=f"meal_note_{ds}", disabled=is_closed)
        up = st.file_uploader("Carica foto del pasto", type=["png", "jpg", "jpeg"], key=f"meal_photo_{ds}", disabled=is_closed)
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
                recompute_daily_summary(user_id, d)
                st.rerun()

    st.subheader("📌 Pasti registrati")
meals = safe_read_sql(
    "SELECT id, time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
    (user_id, ds)
)

if meals.empty:
    st.caption("Nessun pasto registrato.")
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
                recompute_daily_summary(user_id, d)
                st.rerun()

    # WORKOUT
    st.divider()
    st.subheader("🏃 Allenamento fatto (stima calorie)")
    wtab_txt, wtab_manual = st.tabs(["✍️ Da testo", "🧾 Manuale"])

    prof = get_profile(user_id) or {}
    prof_weight = float(prof.get("start_weight") or 75.0)
    prof_height = float(prof.get("height_cm") or 175.0)

    with wtab_txt:
        w_time = st.text_input("Ora allenamento", value="19:00", key=f"w_time_txt_{ds}", disabled=is_closed)
        w_text = st.text_area("Descrivi allenamento", key=f"w_desc_{ds}", height=110, disabled=is_closed)
        if st.button("Stima e salva allenamento", key=f"w_est_save_{ds}", disabled=is_closed):
            if not (w_text or "").strip():
                st.error("Scrivi una descrizione dell'allenamento.")
            else:
                data = estimate_workout_from_text(w_text, prof_weight, prof_height)
                kcal_burned = float(data.get("calories_burned") or 0)
                conn.execute(
                    """
                    INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (user_id, ds, w_time, w_text, None, kcal_burned, str(data))
                )
                conn.commit()
                recompute_daily_summary(user_id, d)
                st.rerun()

    with wtab_manual:
        w_time2 = st.text_input("Ora", value="19:00", key=f"w_time_m_{ds}", disabled=is_closed)
        w_title = st.text_input("Titolo", value="Allenamento", key=f"w_title_m_{ds}", disabled=is_closed)
        w_dur = st.number_input("Durata (min)", min_value=0, value=45, step=5, key=f"w_dur_m_{ds}", disabled=is_closed)
        w_kcal = st.number_input("Calorie bruciate (se le sai)", min_value=0, value=0, step=10, key=f"w_kcal_m_{ds}", disabled=is_closed)
        if st.button("💾 Salva allenamento", key=f"w_save_m_{ds}", disabled=is_closed):
            kcal_burned = float(w_kcal) if w_kcal > 0 else 0.0
            conn.execute(
                """
                INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json)
                VALUES (?,?,?,?,?,?,?)
                """,
                (user_id, ds, w_time2, w_title, int(w_dur), kcal_burned, None)
            )
            conn.commit()
            recompute_daily_summary(user_id, d)
            st.rerun()
st.subheader("📌 Allenamenti registrati")
workouts = safe_read_sql(
    "SELECT id, time, description, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
    (user_id, ds)
)

if workouts.empty:
    st.caption("Nessun allenamento registrato.")
else:
    for _, r in workouts.iterrows():
        c1, c2 = st.columns([8, 2])
        with c1:
            dur = f" — {int(r['duration_min'])} min" if pd.notna(r["duration_min"]) else ""
            st.markdown(f"**{r['time']}** — {r['description']}{dur}")
            st.caption(f"{kcal_round(r['calories_burned'])} kcal")
        with c2:
            if st.button("🗑️", key=f"delw_{ds}_{int(r['id'])}", disabled=is_closed):
                conn.execute("DELETE FROM workouts WHERE user_id=? AND id=?", (user_id, int(r["id"])))
                conn.commit()
                recompute_daily_summary(user_id, d)
                st.rerun()

# ----------------------------
# Weekly plan (placeholder)
# ----------------------------
def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale")
    st.caption("Se vuoi reintegro qui la tua weekly_plan completa senza toccare il resto.")