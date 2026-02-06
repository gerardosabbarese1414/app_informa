import streamlit as st
from datetime import date
from database import conn

def get_profile(uid):
    r = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (uid,)).fetchone()
    if not r: return None
    cols = [d[0] for d in conn.execute("PRAGMA table_info(user_profile)")]
    return dict(zip(cols, r))

def profile_page(uid):
    st.header("Profilo")

    p = get_profile(uid) or {}

    weight = st.number_input("Peso iniziale", value=float(p.get("start_weight") or 0))
    height = st.number_input("Altezza cm", value=float(p.get("height_cm") or 0))
    sex = st.selectbox("Sesso", ["M","F"])
    age = st.number_input("Età", value=int(p.get("age") or 25))
    level = st.selectbox("Attività", ["sedentario","leggero","moderato","alto"])
    goal = st.selectbox("Obiettivo", ["Dimagrimento","Mantenimento","Massa"])
    goal_date = st.date_input("Data obiettivo", value=date.today())

    if st.button("Salva"):
        conn.execute("""
        INSERT INTO user_profile VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        start_weight=?,height_cm=?,sex=?,age=?,activity_level=?,goal_type=?,goal_date=?
        """,(uid,weight,height,sex,age,None,None,level,goal,None,str(goal_date),
             weight,height,sex,age,level,goal,str(goal_date)))
        conn.commit()
        st.success("Profilo salvato")