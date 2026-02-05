import streamlit as st
import pandas as pd
import plotly.express as px
import calendar as cal
from datetime import date, datetime, timedelta
from database import conn
from ai import analyze_food_photo, generate_weekly_plan

def _iso_year_week(d: date):
    y, w, _ = d.isocalendar()
    return y, w

def _fetch_day_preview(user_id: int, d: date):
    ds = str(d)
    day = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    sums = conn.execute(
        "SELECT calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    return {
        "weight": day[0] if day else None,
        "closed": bool(day[1]) if day else False,
        "kcal_in": sums[0] if sums else None,
        "kcal_out": sums[1] if sums else None,
        "net": sums[2] if sums else None,
    }

def month_calendar(user_id: int):
    st.header("📅 Calendario mese")

    if "selected_date" not in st.session_state:
        st.session_state.selected_date = date.today()

    colA, colB = st.columns([1, 1])
    with colA:
        year = st.number_input("Anno", min_value=2020, max_value=2100, value=st.session_state.selected_date.year, step=1)
    with colB:
        month = st.number_input("Mese", min_value=1, max_value=12, value=st.session_state.selected_date.month, step=1)

    month_matrix = cal.monthcalendar(year, month)
    st.caption("Clicca un giorno per aprire la giornata. Anteprima: peso / kcal (se giorno chiuso).")

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

            d = date(year, month, day_num)
            p = _fetch_day_preview(user_id, d)

            badge = "✅" if p["closed"] else "•"
            line1 = f"{badge} **{day_num}**"
            line2 = ""
            if p["weight"] is not None:
                line2 += f"\n{p['weight']:.1f} kg"
            if p["kcal_in"] is not None:
                line2 += f"\n{kcal_round(p['kcal_in'])} kcal"

            if cols[i].button(f"{day_num}", key=f"daybtn_{year}_{month}_{day_num}", use_container_width=True):
                st.session_state.selected_date = d
                st.rerun()

            cols[i].markdown(f"{line1}{line2}")

    st.divider()
    day_detail(user_id, st.session_state.selected_date)

def kcal_round(x):
    try:
        return int(round(float(x)))
    except Exception:
        return x

def _upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    ds = str(d)
    existing = conn.execute("SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?", (user_id, ds)).fetchone()
    if existing:
        mw = morning_weight if morning_weight is not None else existing[0]
        ic = is_closed if is_closed is not None else existing[1]
        conn.execute("UPDATE day_logs SET morning_weight=?, is_closed=? WHERE user_id=? AND date=?", (mw, ic, user_id, ds))
    else:
        conn.execute("INSERT INTO day_logs (user_id, date, morning_weight, is_closed) VALUES (?,?,?,?)",
                     (user_id, ds, morning_weight, int(is_closed or 0)))
    conn.commit()

def _estimate_workout_calories(activity: str, duration_min: int, weight_kg: float | None):
    # Stima semplice (MET grossolano)
    met_map = {
        "corsa": 9.8,
        "camminata": 3.5,
        "pesi": 6.0,
        "bicicletta": 7.5,
        "nuoto": 8.0,
        "calcio": 8.0,
        "hiit": 10.0,
        "yoga": 3.0,
    }
    met = met_map.get(activity.strip().lower(), 5.0)
    w = weight_kg or 75.0
    # kcal = MET * 3.5 * kg / 200 * min
    return met * 3.5 * w / 200.0 * duration_min

def day_detail(user_id: int, d: date):
    ds = str(d)
    st.subheader(f"🗓️ Giornata: {ds}")

    row = conn.execute("SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?", (user_id, ds)).fetchone()
    morning_weight = row[0] if row else None
    is_closed = bool(row[1]) if row else False

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla (sbloccare) se vuoi modificare e richiudere.")
        if st.button("🔓 Riapri giornata"):
            _upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    # Peso mattina
    st.markdown("### ⚖️ Peso mattina")
    w = st.number_input("Peso (kg)", value=float(morning_weight) if morning_weight is not None else 0.0, step=0.1, disabled=is_closed)
    if st.button("Salva peso", disabled=is_closed):
        _upsert_day_log(user_id, d, morning_weight=w, is_closed=0)
        st.success("Peso salvato")

    st.markdown("### 🍽️ Pasti (foto → calorie)")
    up = st.file_uploader("Carica foto del cibo", type=["jpg", "jpeg", "png"], disabled=is_closed)
    if up and not is_closed:
        mime = up.type or "image/jpeg"
        with st.spinner("Analizzo la foto e stimo le calorie..."):
            result = analyze_food_photo(up.getvalue(), mime=mime)

        total = result.get("total_calories", 0) or 0
        notes = result.get("notes", "")
        items = result.get("items", [])

        st.success(f"Stima totale: **{kcal_round(total)} kcal**")
        if notes:
            st.caption(notes)

        desc = ", ".join([f"{it.get('name','')} ({it.get('portion','')})" for it in items]) if items else "Pasto (stima)"
        time_str = datetime.now().strftime("%H:%M")

        if st.button("✅ Aggiungi al giorno"):
            conn.execute(
                "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                (user_id, ds, time_str, desc, float(total), str(result))
            )
            conn.commit()
            st.rerun()

    meals = pd.read_sql(
        "SELECT time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        conn, params=(user_id, ds)
    )
    if not meals.empty:
        st.dataframe(meals, use_container_width=True)
        st.metric("Totale calorie ingerite", f"{kcal_round(meals['calories'].sum())} kcal")
    else:
        st.caption("Nessun pasto inserito ancora.")

    st.markdown("### 🏃 Allenamento")
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        activity = st.text_input("Attività (es: corsa, pesi, camminata)", disabled=is_closed)
    with c2:
        duration = st.number_input("Durata (min)", min_value=0, value=0, step=5, disabled=is_closed)
    with c3:
        add_workout = st.button("Aggiungi", disabled=is_closed)

    if add_workout and not is_closed and activity and duration > 0:
        kcal_b = _estimate_workout_calories(activity, int(duration), w if w > 0 else morning_weight)
        time_str = datetime.now().strftime("%H:%M")
        conn.execute(
            "INSERT INTO workouts (user_id, date, time, activity, duration_min, calories_burned) VALUES (?,?,?,?,?,?)",
            (user_id, ds, time_str, activity, int(duration), float(kcal_b))
        )
        conn.commit()
        st.rerun()

    workouts = pd.read_sql(
        "SELECT time, activity, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        conn, params=(user_id, ds)
    )
    if not workouts.empty:
        st.dataframe(workouts, use_container_width=True)
        st.metric("Totale calorie bruciate (stima)", f"{kcal_round(workouts['calories_burned'].sum())} kcal")
    else:
        st.caption("Nessun allenamento inserito ancora.")

    st.divider()

    # Chiudi giornata + riepilogo
    st.markdown("### ✅ Chiudi giornata e salva riepilogo")
    total_in = float(meals["calories"].sum()) if not meals.empty else 0.0
    total_out = float(workouts["calories_burned"].sum()) if not workouts.empty else 0.0
    net = total_in - total_out

    st.write(f"**Riepilogo provvisorio:** In: {kcal_round(total_in)} kcal — Out: {kcal_round(total_out)} kcal — Net: {kcal_round(net)} kcal")

    if st.button("🔒 Chiudi giornata", disabled=is_closed):
        _upsert_day_log(user_id, d, morning_weight=w if w > 0 else morning_weight, is_closed=1)
        conn.execute(
            "REPLACE INTO daily_summaries (user_id, date, calories_in, calories_out, net_calories) VALUES (?,?,?,?,?)",
            (user_id, ds, total_in, total_out, net)
        )
        conn.commit()
        st.success("Giornata chiusa e riepilogo salvato ✅")
        st.rerun()

def dashboard(user_id: int):
    st.header("📊 Dashboard")

    weights = pd.read_sql("SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND morning_weight IS NOT NULL ORDER BY date",
                          conn, params=(user_id,))
    sums = pd.read_sql("SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? ORDER BY date",
                       conn, params=(user_id,))

    c1, c2, c3 = st.columns(3)
    if not weights.empty:
        c1.metric("Peso ultimo", f"{weights.iloc[-1]['weight']:.1f} kg")
        if len(weights) >= 2:
            c2.metric("Delta ultimi 7gg", f"{(weights['weight'].iloc[-1]-weights['weight'].iloc[max(0,len(weights)-7)]):+.1f} kg")
    else:
        c1.metric("Peso ultimo", "—")
        c2.metric("Delta ultimi 7gg", "—")

    if not sums.empty:
        c3.metric("Net calorie ultimo giorno", f"{kcal_round(sums.iloc[-1]['net_calories'])} kcal")
    else:
        c3.metric("Net calorie ultimo giorno", "—")

    if not weights.empty:
        figw = px.line(weights, x="date", y="weight", title="Peso nel tempo")
        st.plotly_chart(figw, use_container_width=True)

    if not sums.empty:
        figc = px.bar(sums.tail(30), x="date", y=["calories_in", "calories_out"], barmode="group", title="Calorie In/Out (ultimi 30 giorni)")
        st.plotly_chart(figc, use_container_width=True)

        fignet = px.line(sums.tail(30), x="date", y="net_calories", title="Net calorie (ultimi 30 giorni)")
        st.plotly_chart(fignet, use_container_width=True)

def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale (adattivo)")

    today = date.today()
    y, w = _iso_year_week(today)

    # Riassunto automatico: ultimi 7 giorni chiusi
    last7_start = today - timedelta(days=7)
    sums = pd.read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date>=? ORDER BY date",
        conn, params=(user_id, str(last7_start))
    )
    weights = pd.read_sql(
        "SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND date>=? AND morning_weight IS NOT NULL ORDER BY date",
        conn, params=(user_id, str(last7_start))
    )

    summary_lines = []
    if not weights.empty:
        summary_lines.append(f"Peso inizio periodo: {weights.iloc[0]['weight']:.1f} kg")
        summary_lines.append(f"Peso fine periodo: {weights.iloc[-1]['weight']:.1f} kg")
        summary_lines.append(f"Variazione: {(weights.iloc[-1]['weight']-weights.iloc[0]['weight']):+.1f} kg")
    if not sums.empty:
        summary_lines.append(f"Media calorie IN: {sums['calories_in'].mean():.0f}")
        summary_lines.append(f"Media calorie OUT: {sums['calories_out'].mean():.0f}")
        summary_lines.append(f"Media NET: {sums['net_calories'].mean():.0f}")
        summary_lines.append(f"Giorni tracciati: {len(sums)}")

    summary_text = "\n".join(summary_lines) if summary_lines else "Nessun dato disponibile negli ultimi 7 giorni. Inserisci e chiudi almeno qualche giornata."

    st.markdown("### Dati usati per generare il piano")
    st.code(summary_text)

    if st.button("🔄 Genera piano per questa settimana"):
        with st.spinner("Creo il piano..."):
            content = generate_weekly_plan(summary_text)
        conn.execute(
            "REPLACE INTO weekly_plan (user_id, iso_year, iso_week, content, created_at) VALUES (?,?,?,?,?)",
            (user_id, y, w, content, datetime.now().isoformat(timespec="seconds"))
        )
        conn.commit()
        st.success("Piano generato ✅")

    row = conn.execute(
        "SELECT content, created_at FROM weekly_plan WHERE user_id=? AND iso_year=? AND iso_week=?",
        (user_id, y, w)
    ).fetchone()

    if row:
        st.caption(f"Creato: {row[1]}")
        st.markdown(row[0])
    else:
        st.info("Nessun piano salvato per questa settimana.")