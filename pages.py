import streamlit as st
import pandas as pd
import plotly.express as px
import calendar as cal
from datetime import date, datetime, timedelta

from database import conn
from ai import analyze_food_photo, generate_weekly_plan
from openai import RateLimitError

def kcal_round(x):
    try:
        return int(round(float(x)))
    except Exception:
        return x

def safe_read_sql(query, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()

def _iso_year_week(d: date):
    y, w, _ = d.isocalendar()
    return y, w

def _upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    ds = str(d)
    existing = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    if existing:
        mw = morning_weight if morning_weight is not None else existing[0]
        ic = int(is_closed) if is_closed is not None else existing[1]
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

def _estimate_workout_calories(activity: str, duration_min: int, weight_kg: float | None):
    met_map = {
        "corsa": 9.8, "camminata": 3.5, "pesi": 6.0, "bicicletta": 7.5,
        "nuoto": 8.0, "calcio": 8.0, "hiit": 10.0, "yoga": 3.0
    }
    met = met_map.get(activity.strip().lower(), 5.0)
    w = weight_kg or 75.0
    return met * 3.5 * w / 200.0 * duration_min

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

    cA, cB = st.columns([1, 1])
    with cA:
        year = st.number_input("Anno", 2020, 2100, st.session_state.selected_date.year, 1)
    with cB:
        month = st.number_input("Mese", 1, 12, st.session_state.selected_date.month, 1)

    month_matrix = cal.monthcalendar(year, month)
    st.caption("Anteprima: ✅=giorno chiuso. Sotto: peso e kcal ingerite (se giornata chiusa).")

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
            preview = f"{badge} **{day_num}**"
            if p["weight"] is not None:
                preview += f"\n{p['weight']:.1f} kg"
            if p["kcal_in"] is not None:
                preview += f"\n{kcal_round(p['kcal_in'])} kcal"

            if cols[i].button(f"{day_num}", key=f"daybtn_{year}_{month}_{day_num}", use_container_width=True):
                st.session_state.selected_date = d
                st.rerun()

            cols[i].markdown(preview)

    st.divider()
    day_detail(user_id, st.session_state.selected_date)

def day_detail(user_id: int, d: date):
    ds = str(d)
    st.subheader(f"🗓️ Giornata: {ds}")

    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    morning_weight = row[0] if row else None
    is_closed = bool(row[1]) if row else False

    if is_closed:
        st.info("Giornata chiusa. Puoi riaprirla per modifiche.")
        if st.button("🔓 Riapri giornata"):
            _upsert_day_log(user_id, d, is_closed=0)
            st.rerun()

    st.markdown("### ⚖️ Peso mattina")
    w = st.number_input(
        "Peso (kg)", step=0.1,
        value=float(morning_weight) if morning_weight is not None else 0.0,
        disabled=is_closed
    )
    if st.button("Salva peso", disabled=is_closed):
        _upsert_day_log(user_id, d, morning_weight=w, is_closed=0)
        st.success("Peso salvato ✅")

    st.markdown("### 🍽️ Pasti")

    # Upload foto
    st.markdown("#### 📷 Da foto (calorie stimate)")
    up = st.file_uploader("Carica foto del cibo", type=["jpg", "jpeg", "png"], disabled=is_closed)
    if up and not is_closed:
        # anti doppio-click: salva risultato in sessione
        key = f"last_food_result_{ds}"
        if key not in st.session_state:
            with st.spinner("Analizzo la foto e stimo le calorie..."):
                try:
                    st.session_state[key] = analyze_food_photo(up.getvalue(), mime=up.type or "image/jpeg")
                except RateLimitError:
                    st.error("Troppe richieste a ChatGPT in poco tempo. Riprova tra 30-60 secondi.")
                    return

        result = st.session_state[key]
        total = float(result.get("total_calories", 0) or 0)
        notes = result.get("notes", "")
        items = result.get("items", [])

        st.success(f"Stima totale: **{kcal_round(total)} kcal**")
        if notes:
            st.caption(notes)

        desc = ", ".join([f"{it.get('name','')} ({it.get('portion','')})" for it in items]) if items else "Pasto (stima foto)"
        time_str = datetime.now().strftime("%H:%M")

        if st.button("✅ Aggiungi questo pasto al giorno"):
            conn.execute(
                "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                (user_id, ds, time_str, desc, total, str(result))
            )
            conn.commit()
            # pulisci cache per evitare reinserimenti involontari
            del st.session_state[key]
            st.rerun()

    # Manuale
    st.markdown("#### ✍️ Manuale (senza foto)")
    m1, m2, m3 = st.columns([1, 2, 1])
    with m1:
        meal_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), key=f"meal_time_{ds}", disabled=is_closed)
    with m2:
        meal_desc = st.text_input("Descrizione", key=f"meal_desc_{ds}", disabled=is_closed)
    with m3:
        meal_kcal = st.number_input("Kcal", min_value=0, value=0, step=50, key=f"meal_kcal_{ds}", disabled=is_closed)

    if st.button("➕ Aggiungi pasto", key=f"add_meal_manual_{ds}", disabled=is_closed):
        if meal_desc.strip() == "":
            st.error("Inserisci una descrizione del pasto.")
        else:
            conn.execute(
                "INSERT INTO meals (user_id, date, time, description, calories, raw_json) VALUES (?,?,?,?,?,?)",
                (user_id, ds, meal_time, meal_desc.strip(), float(meal_kcal), None)
            )
            conn.commit()
            st.success("Pasto aggiunto ✅")
            st.rerun()

    meals = safe_read_sql(
        "SELECT time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    if not meals.empty:
        st.dataframe(meals, use_container_width=True)
        total_in = float(meals["calories"].fillna(0).sum())
    else:
        st.caption("Nessun pasto inserito ancora.")
        total_in = 0.0

    st.metric("Totale calorie ingerite", f"{kcal_round(total_in)} kcal")

    st.markdown("### 🏃 Allenamento")
    a1, a2, a3, a4 = st.columns([2, 1, 1, 1])
    with a1:
        activity = st.text_input("Attività", disabled=is_closed, key=f"act_{ds}")
    with a2:
        duration = st.number_input("Durata (min)", min_value=0, value=0, step=5, disabled=is_closed, key=f"dur_{ds}")
    with a3:
        w_time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"), disabled=is_closed, key=f"wtime_{ds}")
    with a4:
        kcal_manual = st.number_input("Kcal (opz.)", min_value=0, value=0, step=25, disabled=is_closed, key=f"kcalw_{ds}")

    if st.button("➕ Aggiungi allenamento", disabled=is_closed, key=f"add_work_{ds}"):
        if activity.strip() == "" or duration <= 0:
            st.error("Inserisci attività e durata.")
        else:
            kcal_b = float(kcal_manual) if kcal_manual > 0 else _estimate_workout_calories(activity, int(duration), w if w > 0 else morning_weight)
            conn.execute(
                "INSERT INTO workouts (user_id, date, time, activity, duration_min, calories_burned) VALUES (?,?,?,?,?,?)",
                (user_id, ds, w_time, activity.strip(), int(duration), float(kcal_b))
            )
            conn.commit()
            st.success("Allenamento aggiunto ✅")
            st.rerun()

    workouts = safe_read_sql(
        "SELECT time, activity, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    if not workouts.empty:
        st.dataframe(workouts, use_container_width=True)
        total_out = float(workouts["calories_burned"].fillna(0).sum())
    else:
        st.caption("Nessun allenamento inserito ancora.")
        total_out = 0.0

    st.metric("Totale calorie bruciate (stima)", f"{kcal_round(total_out)} kcal")

    st.divider()
    st.markdown("### ✅ Chiudi giornata e salva riepilogo")

    net = total_in - total_out
    st.write(f"**Riepilogo:** In {kcal_round(total_in)} — Out {kcal_round(total_out)} — Net {kcal_round(net)} kcal")

    if st.button("🔒 Chiudi giornata", disabled=is_closed):
        _upsert_day_log(user_id, d, morning_weight=w if w > 0 else morning_weight, is_closed=1)
        conn.execute(
            "REPLACE INTO daily_summaries (user_id, date, calories_in, calories_out, net_calories) VALUES (?,?,?,?,?)",
            (user_id, ds, total_in, total_out, net)
        )
        conn.commit()
        st.success("Giornata chiusa ✅")
        st.rerun()

def dashboard(user_id: int):
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

    if not weights.empty and len(weights) >= 2:
        c2.metric("Delta ultimi 7gg", f"{(weights.iloc[-1]['weight']-weights.iloc[max(0,len(weights)-7)]['weight']):+.1f} kg")
    else:
        c2.metric("Delta ultimi 7gg", "—")

    c3.metric("Net calorie ultimo giorno", f"{kcal_round(sums.iloc[-1]['net_calories'])} kcal" if not sums.empty else "—")

    if not weights.empty:
        st.plotly_chart(px.line(weights, x="date", y="weight", title="Peso nel tempo"), use_container_width=True)

    if not sums.empty:
        st.plotly_chart(px.bar(sums.tail(30), x="date", y=["calories_in","calories_out"], barmode="group",
                               title="Calorie IN/OUT (ultimi 30 giorni)"),
                        use_container_width=True)
        st.plotly_chart(px.line(sums.tail(30), x="date", y="net_calories", title="Net calorie (ultimi 30 giorni)"),
                        use_container_width=True)

def weekly_plan_page(user_id: int):
    st.header("🧠 Piano settimanale")

    today = date.today()
    y, w = _iso_year_week(today)
    last7_start = today - timedelta(days=7)

    sums = safe_read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? AND date>=? ORDER BY date",
        (user_id, str(last7_start))
    )
    weights = safe_read_sql(
        "SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND date>=? AND morning_weight IS NOT NULL ORDER BY date",
        (user_id, str(last7_start))
    )

    lines = []
    if not weights.empty:
        lines += [
            f"Peso inizio: {weights.iloc[0]['weight']:.1f} kg",
            f"Peso fine: {weights.iloc[-1]['weight']:.1f} kg",
            f"Variazione: {(weights.iloc[-1]['weight']-weights.iloc[0]['weight']):+.1f} kg",
        ]
    if not sums.empty:
        lines += [
            f"Giorni tracciati: {len(sums)}",
            f"Media calorie IN: {sums['calories_in'].mean():.0f}",
            f"Media calorie OUT: {sums['calories_out'].mean():.0f}",
            f"Media NET: {sums['net_calories'].mean():.0f}",
        ]

    summary_text = "\n".join(lines) if lines else "Dati insufficienti: chiudi almeno 2-3 giornate per generare un piano sensato."
    st.markdown("### Dati usati")
    st.code(summary_text)

    # Cache DB: se esiste già per questa settimana, mostralo senza chiamare OpenAI
    existing = conn.execute(
        "SELECT content, created_at FROM weekly_plan WHERE user_id=? AND iso_year=? AND iso_week=?",
        (user_id, y, w)
    ).fetchone()

    if existing:
        st.caption(f"Creato: {existing[1]}")
        st.markdown(existing[0])
        if st.button("Rigenera (nuova chiamata a ChatGPT)"):
            existing = None

    if not existing:
        if st.button("🔄 Genera piano"):
            # anti doppio click
            if st.session_state.get("generating_weekly", False):
                st.warning("Generazione già in corso…")
                return
            st.session_state["generating_weekly"] = True

            with st.spinner("Creo il piano…"):
                try:
                    content = generate_weekly_plan(summary_text)
                except RateLimitError:
                    st.session_state["generating_weekly"] = False
                    st.error("Rate limit OpenAI: troppe richieste o quota esaurita. Riprova tra 1-2 minuti.")
                    st.stop()
                except Exception:
                    st.session_state["generating_weekly"] = False
                    st.error("Errore nel generare il piano. Controlla i log Streamlit Cloud.")
                    st.stop()

            conn.execute(
                "REPLACE INTO weekly_plan (user_id, iso_year, iso_week, content, created_at) VALUES (?,?,?,?,?)",
                (user_id, y, w, content, datetime.now().isoformat(timespec="seconds"))
            )
            conn.commit()
            st.session_state["generating_weekly"] = False
            st.success("Piano generato ✅")
            st.rerun()