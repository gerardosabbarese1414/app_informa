import streamlit as st
from datetime import date, datetime
from database import conn

def get_profile(uid: int):
    row = conn.execute("""
        SELECT user_id, start_weight, height_cm, sex, age,
               body_fat_pct, lean_mass_kg, activity_level,
               goal_type, goal_weight, goal_date, updated_at
        FROM user_profile
        WHERE user_id=?
    """, (uid,)).fetchone()

    if not row:
        return None

    keys = ["user_id","start_weight","height_cm","sex","age",
            "body_fat_pct","lean_mass_kg","activity_level",
            "goal_type","goal_weight","goal_date","updated_at"]
    return dict(zip(keys, row))

def profile_page(uid: int):
    st.header("👤 Profilo")

    p = get_profile(uid) or {}

    start_weight = st.number_input("Peso di partenza (kg)", value=float(p.get("start_weight") or 0.0), step=0.1)
    height_cm = st.number_input("Altezza (cm)", value=float(p.get("height_cm") or 0.0), step=1.0)

    c1, c2 = st.columns(2)
    with c1:
        sex = st.selectbox("Sesso", ["M", "F"], index=0 if (p.get("sex") or "M") == "M" else 1)
    with c2:
        age = st.number_input("Età", min_value=10, max_value=100, value=int(p.get("age") or 25), step=1)

    st.subheader("Composizione corporea (opzionale)")
    body_fat_pct = st.number_input("Massa grassa (%)", value=float(p.get("body_fat_pct") or 0.0), step=0.1)
    lean_mass_kg = st.number_input("Massa magra (kg)", value=float(p.get("lean_mass_kg") or 0.0), step=0.1)

    st.subheader("Stile di vita")
    activity_level = st.selectbox(
        "Livello attività",
        ["sedentario", "leggero", "moderato", "alto"],
        index=["sedentario","leggero","moderato","alto"].index((p.get("activity_level") or "leggero"))
    )

    st.subheader("🎯 Obiettivo")
    goal_type = st.selectbox(
        "Tipo obiettivo",
        ["Dimagrimento", "Mantenimento", "Massa muscolare"],
        index=["Dimagrimento","Mantenimento","Massa muscolare"].index((p.get("goal_type") or "Dimagrimento"))
    )
    goal_weight = st.number_input("Peso obiettivo (kg) (opzionale)", value=float(p.get("goal_weight") or 0.0), step=0.1)

    default_date = date.fromisoformat(p["goal_date"]) if p.get("goal_date") else date.today()
    goal_date = st.date_input("Data obiettivo", value=default_date)

    if st.button("💾 Salva profilo"):
        conn.execute("""
            INSERT INTO user_profile
              (user_id, start_weight, height_cm, sex, age,
               body_fat_pct, lean_mass_kg, activity_level,
               goal_type, goal_weight, goal_date, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              start_weight=excluded.start_weight,
              height_cm=excluded.height_cm,
              sex=excluded.sex,
              age=excluded.age,
              body_fat_pct=excluded.body_fat_pct,
              lean_mass_kg=excluded.lean_mass_kg,
              activity_level=excluded.activity_level,
              goal_type=excluded.goal_type,
              goal_weight=excluded.goal_weight,
              goal_date=excluded.goal_date,
              updated_at=excluded.updated_at
        """, (
            uid,
            start_weight if start_weight > 0 else None,
            height_cm if height_cm > 0 else None,
            sex,
            int(age),
            body_fat_pct if body_fat_pct > 0 else None,
            lean_mass_kg if lean_mass_kg > 0 else None,
            activity_level,
            goal_type,
            goal_weight if goal_weight > 0 else None,
            str(goal_date),
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit()
        st.success("Profilo salvato ✅")
        st.rerun()