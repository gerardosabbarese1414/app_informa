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
    sex = (sex or "M").upper()
    if sex == "F":
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
    return bmr * factors.get(level, 1.375)


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))