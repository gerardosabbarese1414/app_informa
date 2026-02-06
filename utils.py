from datetime import date

def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    # kcal/day
    if sex.upper() == "M":
        return 10*weight_kg + 6.25*height_cm - 5*age + 5
    return 10*weight_kg + 6.25*height_cm - 5*age - 161

def tdee_from_level(bmr: float, activity_level: str) -> float:
    factors = {
        "sedentario": 1.2,
        "leggero": 1.375,
        "moderato": 1.55,
        "alto": 1.725,
    }
    return bmr * factors.get((activity_level or "leggero").lower(), 1.375)

def iso_year_week(d: date):
    y, w, _ = d.isocalendar()
    return y, w

def kcal_round(x):
    try:
        return int(round(float(x)))
    except Exception:
        return x