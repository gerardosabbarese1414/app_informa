from __future__ import annotations
from datetime import date


def kcal_round(x) -> int:
    try:
        return int(round(float(x)))
    except Exception:
        return 0


def iso_year_week(d: date):
    iso = d.isocalendar()
    return int(iso.year), int(iso.week)


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    s = (sex or "M").upper()
    if s == "F":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5


def tdee_from_level(bmr: float, level: str) -> float:
    level = (level or "leggero").lower()
    factors = {
        "sedentario": 1.2,
        "leggero": 1.375,
        "moderato": 1.55,
        "attivo": 1.725,
        "molto_attivo": 1.9,
    }
    return float(bmr) * factors.get(level, 1.375)


def heuristic_meal_kcal(text: str) -> float:
    t = (text or "").lower()
    base = 500.0
    if "insalata" in t: base = 250
    if "pizza" in t: base = 900
    if "pasta" in t:
        base = 650
        if "pesto" in t: base = 750
        if "integrale" in t: base += 30
    if "pollo" in t or "carne" in t: base = 600
    if "dolce" in t or "gelato" in t: base = 450
    return float(base)


def heuristic_workout_kcal(title: str, duration_min: int) -> float:
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