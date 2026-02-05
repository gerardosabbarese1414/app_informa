import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from database import conn
from ai import generate_weekly_plan

def dashboard(user_id):
    st.header("📊 Dashboard")

    df = pd.read_sql(
        "SELECT date, weight FROM weight WHERE user_id=?",
        conn,
        params=(user_id,)
    )

    if not df.empty:
        fig = px.line(df, x="date", y="weight", title="Peso nel tempo")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Inserisci il peso per vedere i progressi")

def calendar(user_id):
    st.header("📅 Giornata")
    d = st.date_input("Data", date.today())

    peso = st.number_input("Peso (kg)", step=0.1)
    if st.button("Salva peso"):
        conn.execute(
            "INSERT INTO weight VALUES (?,?,?)",
            (user_id, str(d), peso)
        )
        conn.commit()
        st.success("Peso salvato")

    st.subheader("🏃 Allenamento")
    act = st.text_input("Attività")
    dur = st.number_input("Durata (min)", 0)
    if st.button("Salva allenamento"):
        conn.execute(
            "INSERT INTO workouts VALUES (?,?,?,?)",
            (user_id, str(d), act, dur)
        )
        conn.commit()
        st.success("Allenamento salvato")

def weekly_plan(user_id):
    st.header("🥗 Piano Settimanale")

    if st.button("Genera nuovo piano"):
        summary = "Peso medio stabile, 3 allenamenti, obiettivo dimagrimento"
        plan = generate_weekly_plan(summary)

        conn.execute(
            "INSERT INTO weekly_plan VALUES (?,?,?)",
            (user_id, "current", plan)
        )
        conn.commit()

    row = conn.execute(
        "SELECT content FROM weekly_plan WHERE user_id=? ORDER BY rowid DESC",
        (user_id,)
    ).fetchone()

    if row:
        st.markdown(row[0])