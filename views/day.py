# views/day.py
import streamlit as st
import pandas as pd
from datetime import date

from database import conn, init_db
from profile import get_profile
from utils import kcal_round


# ----------------------------
# SQL helpers
# ----------------------------
def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()


def _ensure_selected_date():
    if "selected_date" not in st.session_state or st.session_state.selected_date is None:
        st.session_state.selected_date = date.today()


# ----------------------------
# Day log helpers
# ----------------------------
def upsert_day_log(user_id: int, d: date, morning_weight=None, is_closed=None):
    init_db()
    ds = str(d)

    row = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    if row:
        mw = morning_weight if morning_weight is not None else row["morning_weight"]
        ic = is_closed if is_closed is not None else row["is_closed"]
        conn.execute(
            "UPDATE day_logs SET morning_weight=?, is_closed=? WHERE user_id=? AND date=?",
            (mw, ic, user_id, ds)
        )
    else:
        conn.execute(
            "INSERT INTO day_logs (user_id, date, morning_weight, is_closed) VALUES (?,?,?,?)",
            (user_id, ds, morning_weight, 1 if is_closed else 0)
        )

    conn.commit()


# ----------------------------
# Calorie computation (REST = peso+altezza)
# ----------------------------
def _get_weight_for_rest(user_id: int, d: date) -> float | None:
    """
    Preferisci peso del mattino del giorno; fallback a start_weight del profilo.
    """
    ds = str(d)
    row = conn.execute(
        "SELECT morning_weight FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    if row and row["morning_weight"] is not None:
        try:
            return float(row["morning_weight"])
        except Exception:
            pass

    p = get_profile(user_id)
    w = p.get("start_weight")
    try:
        return float(w) if w is not None else None
    except Exception:
        return None


def _compute_rest_calories(user_id: int, d: date) -> int:
    """
    ✅ Calorie a riposo calcolate in base a PESO + ALTEZZA (richiesta utente).

    Formula usata: Mifflin-St Jeor "neutra"
      BMR = 10*w + 6.25*h - 5*eta
    dove:
      - w = peso (kg)
      - h = altezza (cm)
      - eta: se presente nel profilo la usiamo, altrimenti default (30)
    """
    p = get_profile(user_id)

    weight_kg = _get_weight_for_rest(user_id, d)
    height_cm = p.get("height_cm")

    if weight_kg in (None, 0, "") or height_cm in (None, 0, ""):
        st.warning(
            "Per calcolare le calorie a riposo servono almeno peso e altezza. "
            "Imposta l’altezza nel Profilo e salva il peso del mattino (o start_weight)."
        )
        return 0

    # età: usa quella del profilo se c'è, altrimenti un default stabile
    DEFAULT_AGE = 30
    try:
        age = int(p.get("age")) if p.get("age") not in (None, "", 0) else DEFAULT_AGE
    except Exception:
        age = DEFAULT_AGE

    w = float(weight_kg)
    h = float(height_cm)

    bmr = (10.0 * w) + (6.25 * h) - (5.0 * age)

    return int(kcal_round(bmr))


def _sum_meals_kcal(user_id: int, d: date) -> float:
    init_db()
    ds = str(d)
    row = conn.execute(
        "SELECT COALESCE(SUM(calories), 0) AS s FROM meals WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()
    return float(row["s"]) if row and row["s"] is not None else 0.0


def _sum_workouts_kcal(user_id: int, d: date) -> float:
    init_db()
    ds = str(d)
    row = conn.execute(
        "SELECT COALESCE(SUM(calories_burned), 0) AS s FROM workouts WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()
    return float(row["s"]) if row and row["s"] is not None else 0.0


def compute_and_upsert_daily_summary(user_id: int, d: date):
    """
    Calcola e salva (UPSERT, non distruttivo) il riepilogo giornaliero.
    """
    init_db()
    ds = str(d)

    calories_in = float(_sum_meals_kcal(user_id, d))
    workout_calories = float(_sum_workouts_kcal(user_id, d))
    rest_calories = float(_compute_rest_calories(user_id, d))

    calories_out = rest_calories + workout_calories
    net_calories = calories_in - calories_out

    conn.execute("""
    INSERT INTO daily_summaries
        (user_id, date, calories_in, rest_calories, workout_calories, calories_out, net_calories)
    VALUES
        (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id, date) DO UPDATE SET
        calories_in=excluded.calories_in,
        rest_calories=excluded.rest_calories,
        workout_calories=excluded.workout_calories,
        calories_out=excluded.calories_out,
        net_calories=excluded.net_calories
    """, (user_id, ds, calories_in, rest_calories, workout_calories, calories_out, net_calories))

    conn.commit()

    return {
        "calories_in": calories_in,
        "rest_calories": rest_calories,
        "workout_calories": workout_calories,
        "calories_out": calories_out,
        "net_calories": net_calories,
    }


# ----------------------------
# Render
# ----------------------------
def render(user_id: int, d: date | None = None):
    init_db()
    _ensure_selected_date()

    if d is None:
        d = st.session_state.selected_date
    else:
        st.session_state.selected_date = d

    st.header("Giornata")

    # Selezione data
    col1, col2 = st.columns([2, 1])
    with col1:
        picked = st.date_input("Data", value=d, key="day_date_input")
        if picked != d:
            st.session_state.selected_date = picked
            st.rerun()

    ds = str(st.session_state.selected_date)
    log = conn.execute(
        "SELECT morning_weight, is_closed FROM day_logs WHERE user_id=? AND date=?",
        (user_id, ds)
    ).fetchone()

    current_weight = log["morning_weight"] if log else None

    with col2:
        mw = st.number_input(
            "Peso mattino (kg)",
            value=float(current_weight) if current_weight is not None else 0.0,
            min_value=0.0,
            step=0.1,
        )
        if st.button("Salva peso"):
            upsert_day_log(user_id, st.session_state.selected_date, morning_weight=mw)
            st.success("Peso salvato.")
            st.rerun()

    st.divider()

    # ✅ Riepilogo calorie (aggiornato a ogni render)
    summary = compute_and_upsert_daily_summary(user_id, st.session_state.selected_date)

    a, b, c, dcol, e = st.columns(5)
    a.metric("Calorie IN", int(round(summary["calories_in"])))
    b.metric("Riposo", int(round(summary["rest_calories"])))
    c.metric("Allenamento", int(round(summary["workout_calories"])))
    dcol.metric("Calorie OUT", int(round(summary["calories_out"])))
    e.metric("Netto", int(round(summary["net_calories"])))

    st.divider()

    # Debug / dettaglio (puoi rimuoverlo)
    meals = safe_read_sql(
        "SELECT time, description, calories FROM meals WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    workouts = safe_read_sql(
        "SELECT time, description, duration_min, calories_burned FROM workouts WHERE user_id=? AND date=? ORDER BY time",
        (user_id, ds)
    )
    with st.expander("Pasti"):
        st.dataframe(meals, use_container_width=True)
    with st.expander("Allenamenti"):
        st.dataframe(workouts, use_container_width=True)