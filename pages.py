import streamlit as st
from datetime import date, datetime
from database import conn
from ai import analyze_food_photo, estimate_from_text
from utils import bmr_mifflin, tdee
from profile import get_profile

def calendar_page(uid):
    d = st.date_input("Giorno", value=date.today())
    day_page(uid, d)

def day_page(uid, d):
    st.subheader(str(d))

    w = st.number_input("Peso mattina", step=0.1)

    note = st.text_input("Nota pasto")
    time = st.text_input("Orario", value=datetime.now().strftime("%H:%M"))
    img = st.file_uploader("Foto pasto", type=["jpg","png"])

    if img and st.button("Stima foto"):
        res = analyze_food_photo(img.getvalue(), img.type, note)
        st.write(res)
        if st.button("Salva pasto"):
            conn.execute("INSERT INTO meals VALUES (NULL,?,?,?,?,?,?)",
                (uid,str(d),time,res["description"],res["total_calories"],str(res)))
            conn.commit()
            st.rerun()

    text = st.text_input("Pasto manuale")
    if st.button("Stima testo"):
        res = estimate_from_text(text)
        st.write(res)