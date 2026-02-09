import streamlit as st
from datetime import datetime, date as ddate
from database import conn


def get_profile(user_id: int) -> dict | None:
    row = conn.execute("""
        SELECT start_weight, height_cm, sex, age, activity_level,
               goal_type, goal_weight, goal_date, body_fat, lean_mass
        FROM user_profile WHERE user_id=?
    """, (user_id,)).fetchone()

    if not row:
        return None

    return {
        "start_weight": row[0],
        "height_cm": row[1],
        "sex": row[2],
        "age": row[3],
        "activity_level": row[4],
        "goal_type": row[5],
        "goal_weight": row[6],
        "goal_date": row[7],
        "body_fat": row[8],
        "lean_mass": row[9],
    }


def profile_complete(user_id: int) -> bool:
    p = get_profile(user_id)
    if not p:
        return False
    required = ["start_weight", "height_cm", "sex", "age", "activity_level", "goal_type", "goal_date"]
    return all(p.get(k) not in (None, "", 0) for k in required)


def profile_page(user_id: int):
    st.header("👤 Profilo iniziale")

    p = get_profile(user_id) or {}

    goal_date_default = None
    if p.get("goal_date"):
        try:
            goal_date_default = ddate.fromisoformat(str(p["goal_date"]))
        except Exception:
            goal_date_default = None

    c1, c2, c3 = st.columns(3)
    with c1:
        start_weight = st.number_input("Peso di partenza (kg)", min_value=0.0, value=float(p.get("start_weight") or 0.0), step=0.1)
        height_cm = st.number_input("Altezza (cm)", min_value=0.0, value=float(p.get("height_cm") or 0.0), step=1.0)
    with c2:
        sex = st.selectbox("Sesso", ["M", "F"], index=0 if (p.get("sex") or "M") == "M" else 1)
        age = st.number_input("Età", min_value=10, max_value=100, value=int(p.get("age") or 25), step=1)
    with c3:
        activity_level = st.selectbox("Livello attività", ["sedentario", "leggero", "moderato", "attivo", "molto_attivo"],
                                      index=["sedentario","leggero","moderato","attivo","molto_attivo"].index((p.get("activity_level") or "leggero").lower()))
        goal_type = st.selectbox("Obiettivo", ["dimagrimento", "mantenimento", "massa"],
                                 index=["dimagrimento","mantenimento","massa"].index((p.get("goal_type") or "mantenimento").lower()
                                       if (p.get("goal_type") or "").lower() in ["dimagrimento","mantenimento","massa"] else 1))

    c4, c5, c6 = st.columns(3)
    with c4:
        goal_weight = st.number_input("Peso obiettivo (kg) (opz.)", min_value=0.0, value=float(p.get("goal_weight") or 0.0), step=0.1)
    with c5:
        goal_date = st.date_input("Data obiettivo", value=goal_date_default)
    with c6:
        body_fat = st.number_input("Massa grassa % (opz.)", min_value=0.0, max_value=80.0, value=float(p.get("body_fat") or 0.0), step=0.5)
        lean_mass = st.number_input("Massa magra kg (opz.)", min_value=0.0, value=float(p.get("lean_mass") or 0.0), step=0.5)

    if st.button("💾 Salva profilo", type="primary"):
        conn.execute("""
            INSERT INTO user_profile
              (user_id, start_weight, height_cm, sex, age, activity_level,
               goal_type, goal_weight, goal_date, body_fat, lean_mass, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                start_weight=excluded.start_weight,
                height_cm=excluded.height_cm,
                sex=excluded.sex,
                age=excluded.age,
                activity_level=excluded.activity_level,
                goal_type=excluded.goal_type,
                goal_weight=excluded.goal_weight,
                goal_date=excluded.goal_date,
                body_fat=excluded.body_fat,
                lean_mass=excluded.lean_mass,
                updated_at=excluded.updated_at
        """, (
            user_id,
            float(start_weight) if start_weight > 0 else None,
            float(height_cm) if height_cm > 0 else None,
            sex,
            int(age) if age > 0 else None,
            activity_level,
            goal_type,
            float(goal_weight) if goal_weight > 0 else None,
            str(goal_date) if goal_date else None,
            float(body_fat) if body_fat > 0 else None,
            float(lean_mass) if lean_mass > 0 else None,
            datetime.now().isoformat(timespec="seconds"),
        ))
        conn.commit()
        st.success("Profilo salvato ✅")
        st.rerun()