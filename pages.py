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
                        use_container_width=True
        )


# ----------------------------
# Month calendar (NO LINK HTML) - usa bottoni Streamlit
# ----------------------------
def month_calendar_page(user_id: int):
    st.header("📅 Calendario (mese)")
    st.caption("Clicca un giorno → apre la Giornata (senza reset della sessione).")

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
    hcols = st.columns(7)
    for i, h in enumerate(headers):
        hcols[i].markdown(f"**{h}**")

    month_matrix = cal.monthcalendar(year, month)
    today = date.today()

    for w, week in enumerate(month_matrix):
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            with cols[i]:
                if day_num == 0:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    st.markdown("<div style='height:90px;border:1px dashed rgba(120,120,120,.18);border-radius:12px;background:rgba(0,0,0,.02)'></div>", unsafe_allow_html=True)
                    continue

                d = date(year, month, int(day_num))
                p = fetch_day_preview(user_id, d)

                badge = "✅" if p["closed"] else "•"
                net_txt = ""
                if p["net"] is not None:
                    net_txt = f"NET {kcal_round(p['net'])}"

                # bottone giorno (chiave unica)
                label = f"{day_num} {badge}"
                if d == today:
                    label = f"⭐ {label}"

                if st.button(label, key=f"daybtn_{d.isoformat()}"):
                    goto_day(d)

                # mini info sotto
                info = []
                if p["weight"] is not None:
                    info.append(f"{float(p['weight']):.1f} kg")
                if net_txt:
                    info.append(net_txt)
                if p["planned"] > 0:
                    info.append(f"🗓️ {p['planned']}")

                if info:
                    st.caption(" • ".join(info))


# ----------------------------
# Day page (Giornata) - con testo + foto
# ----------------------------
def day_page(user_id: int, d: date):
    ds = str(d)
    st.header(f"🗓️ Giornata: {ds}")

    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()
    is_closed = bool(row["is_closed"]) if row else False

    nav1, nav2, nav3 = st.columns([1, 1, 3])
    with nav1:
        if st.button("⬅️ Giorno precedente"):
            goto_day(d - timedelta(days=1))
    with nav2:
        if st.button("Giorno successivo ➡️"):
            goto_day(d + timedelta(days=1))
    with nav3:
        if st.button("⬅️ Torna al Calendario"):
            st.session_state.page = "Calendario"
            st.rerun()

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modificare.")
        if st.button("🔓 Riapri giornata"):
            upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    # PREVISTO
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
                done = st.checkbox("Fatto", value=(status == "done"), key=f"done_{ds}_{int(r['id'])}", disabled=is_closed)
                if done and status != "done" and not is_closed:
                    mark_planned_done_to_actual(user_id, d, r.to_dict())
                    st.rerun()
            with right:
                if st.button("🗑️", key=f"delplanned_{ds}_{int(r['id'])}", disabled=is_closed):
                    delete_planned_event(user_id, int(r["id"]))
                    st.rerun()

    # ✅ PASTO: TESTO / FOTO
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
                st.success(f"Salvato: {int(round(kcal))} kcal")
                st.rerun()

    # mostra pasti salvati
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
# Weekly plan (lasciato come nel tuo progetto)
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
    return "\n".join(lines)


def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale (work in progress)")
    st.caption("Questa sezione resta come nel tuo progetto; se vuoi la reintegro completa dimmelo.")