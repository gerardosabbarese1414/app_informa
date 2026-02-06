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


def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()


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

    return {
        "weight": day[0] if day else None,
        "closed": bool(day[1]) if day else False,
        "in": summ[0] if summ else None,
        "out": summ[1] if summ else None,
        "net": summ[2] if summ else None,
    }


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
        st.plotly_chart(
            px.line(weights, x="date", y="weight", title="Peso nel tempo"),
            use_container_width=True
        )

    if not sums.empty:
        st.plotly_chart(
            px.bar(
                sums.tail(30),
                x="date",
                y=["calories_in", "calories_out"],
                barmode="group",
                title="Calorie IN/OUT (ultimi 30 giorni)"
            ),
            use_container_width=True
        )
        st.plotly_chart(
            px.line(sums.tail(30), x="date", y="net_calories", title="NET (ultimi 30 giorni)"),
            use_container_width=True
        )


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
    st.caption("✅=giorno chiuso. Colore NET: verde (≤0), giallo (0–300), rosso (>300).")

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

            if cols[i].button(f"{day_num}", key=f"day_{year}_{month}_{day_num}", use_container_width=True):
                st.session_state.selected_date = d
                st.rerun()

            preview = f"{badge} **{day_num}**"
            if p["weight"] is not None:
                preview += f"\n{p['weight']:.1f} kg"
            if p["in"] is not None:
                preview += f"\n{kcal_round(p['in'])} kcal"
            if p["net"] is not None:
                preview += f"\n<span class='{color_cls}'>NET {kcal_round(p['net'])}</span>"

            cols[i].markdown(preview, unsafe_allow_html=True)

    st.divider()
    day_page(user_id, st.session_state.selected_date)


def day_page(user_id: int, d: date):
    ds = str(d)
    st.subheader(f"🗓️ Giornata: {ds}")

    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    morning_weight = row[0] if row else None
    is_closed = bool(row[1]) if row else False

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modificare.")
        if st.button("🔓 Riapri giornata"):
            upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    # Peso mattina
    st.markdown("### ⚖️ Peso mattina")
    w = st.number_input(
        "Peso (kg)",
        value=float(morning_weight) if morning_weight is not None else 0.0,
        step=0.1,
        disabled=is_closed
    )
    if st.button("Salva peso", disabled=is_closed):
        upsert_day_log(user_id, d, morning_weight=w, is_closed=0)
        st.success("Peso salvato ✅")

    # Pasti
    st.markdown("### 🍽️ Pasti")

    # Foto pasto
    st.markdown("#### 📷 Da foto")
    f1, f2 = st.columns([1, 2])
    with f1:
        photo_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"pt_{ds}", disabled=is_closed)
    with f2:
        photo_note = st.text_input("Nota (es. 150g pasta, poco pesto)", key=f"pn_{ds}", disabled=is_closed)
    up = st.file_uploader("Carica foto", type=["jpg", "jpeg", "png"], disabled=is_closed, key=f"up_{ds}")

    if up and not is_closed:
        if st.button("🔎 Stima da foto", key=f"an_photo_{ds}"):
            with st.spinner("Analizzo foto..."):
                try:
                    st.session_state[f"photo_res_{ds}"] = analyze_food_photo(
                        up.getvalue(),
                        up.type or "image/jpeg",
                        photo_time,
                        photo_note or ""
                    )
                except Exception as e:
                    st.error(explain_openai_error(e))

        res = st.session_state.get(f"photo_res_{ds}")
        if res and "total_calories" in res:
            st.success(f"Stima: {kcal_round(res.get('total_calories'))} kcal")
            if res.get("notes"):
                st.caption(res.get("notes"))
            if st.button("✅ Aggiungi pasto (foto)", key=f"add_photo_{ds}", disabled=is_closed):
                desc = res.get("description", "Pasto (foto)")
                if photo_note:
                    desc = f"{desc} — Nota: {photo_note}"
                conn.execute(
                    "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                    (user_id, ds, photo_time, desc, float(res.get("total_calories") or 0), str(res))
                )
                conn.commit()
                st.session_state.pop(f"photo_res_{ds}", None)
                st.rerun()

    # Pasto manuale
    st.markdown("#### ✍️ Manuale")
    m1, m2, m3 = st.columns([1, 2, 1])
    with m1:
        meal_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"mt_{ds}", disabled=is_closed)
    with m2:
        meal_text = st.text_input("Cosa hai mangiato", key=f"mtext_{ds}", disabled=is_closed)
    with m3:
        meal_kcal = st.number_input("Kcal (opz.)", min_value=0, value=0, step=50, key=f"mk_{ds}", disabled=is_closed)

    cA, cB = st.columns(2)
    with cA:
        if st.button("🤖 Stima con AI", key=f"est_meal_{ds}", disabled=is_closed):
            try:
                st.session_state[f"meal_ai_{ds}"] = estimate_meal_from_text(meal_text)
            except Exception as e:
                st.error(explain_openai_error(e))

    ai_meal = st.session_state.get(f"meal_ai_{ds}")
    if ai_meal and "total_calories" in ai_meal:
        st.info(f"AI: {kcal_round(ai_meal.get('total_calories'))} kcal — {ai_meal.get('notes','')}")

    with cB:
        if st.button("➕ Aggiungi pasto", key=f"add_meal_{ds}", disabled=is_closed):
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
                st.session_state.pop(f"meal_ai_{ds}", None)
                st.rerun()

    meals = safe_read_sql(
        "SELECT id, time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    total_in = float(meals["calories"].fillna(0).sum()) if not meals.empty else 0.0

    if not meals.empty:
        st.dataframe(meals.drop(columns=["id"]), use_container_width=True)

        del_id = st.number_input(
            "ID pasto da eliminare",
            min_value=0,
            value=0,
            step=1,
            key=f"delmeal_{ds}",
            disabled=is_closed
        )
        if st.button("🗑️ Elimina pasto", disabled=is_closed, key=f"delmealbtn_{ds}"):
            if del_id > 0:
                conn.execute("DELETE FROM meals WHERE user_id=? AND id=?", (user_id, int(del_id)))
                conn.commit()
                st.rerun()

    st.metric("Totale calorie ingerite", f"{kcal_round(total_in)} kcal")

    # Allenamenti
    st.markdown("### 🏃 Allenamento")

    w1, w2 = st.columns([1, 2])
    with w1:
        wo_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"wt_{ds}", disabled=is_closed)
        duration = st.number_input("Durata (min)", min_value=0, value=0, step=5, key=f"wd_{ds}", disabled=is_closed)
    with w2:
        wo_text = st.text_input("Descrizione (es. corsa, pesi)", key=f"wtext_{ds}", disabled=is_closed)
        wo_kcal = st.number_input("Kcal bruciate (opz.)", min_value=0, value=0, step=25, key=f"wk_{ds}", disabled=is_closed)

    prof = get_profile(user_id) or {}
    weight_for_calc = (w if w > 0 else (morning_weight or prof.get("start_weight") or 75.0))
    height_for_calc = (prof.get("height_cm") or 175.0)

    cC, cD = st.columns(2)
    with cC:
        if st.button("🤖 Stima allenamento con AI", key=f"est_wo_{ds}", disabled=is_closed):
            try:
                st.session_state[f"wo_ai_{ds}"] = estimate_workout_from_text(
                    f"{wo_text} per {int(duration)} minuti",
                    float(weight_for_calc) if weight_for_calc else None,
                    float(height_for_calc) if height_for_calc else None
                )
            except Exception as e:
                st.error(explain_openai_error(e))

    ai_wo = st.session_state.get(f"wo_ai_{ds}")
    if ai_wo and "calories_burned" in ai_wo:
        st.info(f"AI: {kcal_round(ai_wo.get('calories_burned'))} kcal — {ai_wo.get('notes','')}")

    with cD:
        if st.button("➕ Aggiungi allenamento", key=f"add_wo_{ds}", disabled=is_closed):
            if not wo_text.strip() or duration <= 0:
                st.error("Inserisci descrizione e durata.")
            else:
                kcal_burn = float(wo_kcal)
                raw = None
                if kcal_burn == 0 and ai_wo and "calories_burned" in ai_wo:
                    kcal_burn = float(ai_wo.get("calories_burned") or 0)
                    raw = str(ai_wo)
                conn.execute(
                    "INSERT INTO workouts (user_id, date, time, description, duration_min, calories_burned, raw_json) VALUES (?,?,?,?,?,?,?)",
                    (user_id, ds, wo_time, wo_text.strip(), int(duration), kcal_burn, raw)
                )
                conn.commit()
                st.session_state.pop(f"wo_ai_{ds}", None)
                st.rerun()

    workouts = safe_read_sql(
        "SELECT id, time, description, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    total_workout = float(workouts["calories_burned"].fillna(0).sum()) if not workouts.empty else 0.0

    if not workouts.empty:
        st.dataframe(workouts.drop(columns=["id"]), use_container_width=True)

        delw_id = st.number_input(
            "ID allenamento da eliminare",
            min_value=0,
            value=0,
            step=1,
            key=f"delwo_{ds}",
            disabled=is_closed
        )
        if st.button("🗑️ Elimina allenamento", disabled=is_closed, key=f"delwobtn_{ds}"):
            if delw_id > 0:
                conn.execute("DELETE FROM workouts WHERE user_id=? AND id=?", (user_id, int(delw_id)))
                conn.commit()
                st.rerun()

    st.metric("Totale calorie bruciate (allenamento)", f"{kcal_round(total_workout)} kcal")

    # TDEE (matematico)
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
    st.markdown("### ✅ Chiudi giornata")
    calories_out = float(rest) + float(total_workout)
    net = float(total_in) - calories_out

    st.write(
        f"IN **{kcal_round(total_in)}** — OUT **{kcal_round(calories_out)}** "
        f"(rest {kcal_round(rest)} + wo {kcal_round(total_workout)}) — NET **{kcal_round(net)}**"
    )

    if st.button("🔒 Chiudi giornata", disabled=is_closed):
        upsert_day_log(user_id, d, morning_weight=(w if w > 0 else morning_weight), is_closed=1)
        conn.execute("""
            REPLACE INTO daily_summaries (user_id, date, calories_in, rest_calories, workout_calories, calories_out, net_calories)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id, ds, float(total_in), float(rest), float(total_workout), float(calories_out), float(net)))
        conn.commit()
        st.success("Giornata chiusa ✅")
        st.rerun()


def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale")

    today = date.today()
    y, w = iso_year_week(today)

    existing = conn.execute(
        "SELECT content, created_at FROM weekly_plan WHERE user_id=? AND iso_year=? AND iso_week=?",
        (user_id, y, w)
    ).fetchone()

    prof = get_profile(user_id) or {}
    last7 = today - timedelta(days=7)

    sums = safe_read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date>=? ORDER BY date",
        (user_id, str(last7))
    )
    weights = safe_read_sql(
        "SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND date>=? AND morning_weight IS NOT NULL ORDER BY date",
        (user_id, str(last7))
    )

    summary_lines = []
    summary_lines.append("PROFILO:")
    summary_lines.append(f"- start_weight: {prof.get('start_weight')}")
    summary_lines.append(f"- height_cm: {prof.get('height_cm')}")
    summary_lines.append(f"- sex: {prof.get('sex')} age: {prof.get('age')} activity: {prof.get('activity_level')}")
    summary_lines.append(f"- goal_type: {prof.get('goal_type')} goal_weight: {prof.get('goal_weight')} goal_date: {prof.get('goal_date')}")
    summary_lines.append("")
    summary_lines.append("ULTIMI 7 GIORNI (chiusi):")

    if not weights.empty:
        summary_lines.append(f"- peso inizio: {weights.iloc[0]['weight']:.1f} kg")
        summary_lines.append(f"- peso fine: {weights.iloc[-1]['weight']:.1f} kg")
        summary_lines.append(f"- variazione: {(weights.iloc[-1]['weight']-weights.iloc[0]['weight']):+.1f} kg")

    if not sums.empty:
        summary_lines.append(f"- giorni tracciati: {len(sums)}")
        summary_lines.append(f"- media IN: {sums['calories_in'].mean():.0f}")
        summary_lines.append(f"- media OUT: {sums['calories_out'].mean():.0f}")
        summary_lines.append(f"- media NET: {sums['net_calories'].mean():.0f}")

    summary_text = "\n".join(summary_lines)
    st.markdown("### Dati usati")
    st.code(summary_text)

    if existing:
        st.caption(f"Creato: {existing[1]}")
        st.markdown(existing[0])
        if st.button("Rigenera (nuova chiamata)"):
            existing = None

    if not existing:
        if st.button("🔄 Genera piano"):
            with st.spinner("Genero piano..."):
                try:
                    content = generate_weekly_plan(summary_text)
                except Exception as e:
                    st.error(explain_openai_error(e))
                    return
            conn.execute(
                "REPLACE INTO weekly_plan (user_id, iso_year, iso_week, content, created_at) VALUES (?,?,?,?,?)",
                (user_id, y, w, content, datetime.now().isoformat(timespec="seconds"))
            )
            conn.commit()
            st.success("Piano generato ✅")
            st.rerun()


def export_month_csv(user_id: int):
    st.header("📤 Export CSV (mese)")
    today = date.today()

    y = st.number_input("Anno", 2020, 2100, today.year, 1)
    m = st.number_input("Mese", 1, 12, today.month, 1)

    start = date(int(y), int(m), 1)
    end = date(int(y), int(m), cal.monthrange(int(y), int(m))[1])

    sums = safe_read_sql(
        "SELECT * FROM daily_summaries WHERE user_id=? AND date>=? AND date<=? ORDER BY date",
        (user_id, str(start), str(end))
    )

    if sums.empty:
        st.info("Nessun dato nel mese selezionato.")
        return

    csv = sums.to_csv(index=False).encode("utf-8")
    st.download_button("Scarica CSV", csv, file_name=f"daily_summaries_{y}_{m}.csv", mime="text/csv")