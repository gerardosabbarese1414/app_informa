import streamlit as st
import json

from ai import estimate_meal_from_text, analyze_food_photo
from db.repo_meals import insert_meal
from utils import kcal_round

def render(user_id: int, ds: str, is_closed: bool):
    st.subheader("➕ Pasti (AI o manuale)")
    tab1, tab2, tab3 = st.tabs(["🧠 Da testo (AI)", "📷 Da foto (AI)", "✍️ Manuale"])

    # AI text
    with tab1:
        m_time = st.text_input("Ora", value="13:00", key=f"meal_ai_time_{ds}", disabled=is_closed)
        m_text = st.text_area("Descrizione libera", value="", key=f"meal_ai_text_{ds}", disabled=is_closed)

        if st.button("Stima con AI", key=f"meal_ai_btn_{ds}", disabled=is_closed):
            est = estimate_meal_from_text(m_text)
            st.session_state[f"meal_ai_est_{ds}"] = est

        est = st.session_state.get(f"meal_ai_est_{ds}")
        if est:
            st.info(f"Stima: {kcal_round(est.get('total_calories', 0))} kcal")
            if est.get("notes"):
                st.caption(f"📝 {est.get('notes')}")
            adj_kcal = st.number_input(
                "Kcal (modificabile)", min_value=0, value=int(round(float(est.get("total_calories") or 0))),
                step=10, key=f"meal_ai_adj_{ds}", disabled=is_closed
            )
            adj_desc = st.text_input(
                "Descrizione (modificabile)", value=(est.get("description") or m_text).strip(),
                key=f"meal_ai_desc_{ds}", disabled=is_closed
            )
            if st.button("Salva pasto", key=f"meal_ai_save_{ds}", disabled=is_closed):
                if not adj_desc.strip():
                    st.error("Inserisci una descrizione.")
                else:
                    insert_meal(user_id, ds, m_time.strip(), adj_desc.strip(), float(adj_kcal), json.dumps(est, ensure_ascii=False))
                    st.session_state.pop(f"meal_ai_est_{ds}", None)
                    st.rerun()

    # AI photo
    with tab2:
        p_time = st.text_input("Ora", value="13:00", key=f"photo_time_{ds}", disabled=is_closed)
        p_note = st.text_input("Nota (opzionale)", value="", key=f"photo_note_{ds}", disabled=is_closed)
        up = st.file_uploader("Carica foto", type=["jpg", "jpeg", "png"], key=f"photo_upl_{ds}", disabled=is_closed)

        if st.button("Analizza foto con AI", key=f"photo_ai_btn_{ds}", disabled=is_closed):
            if up is None:
                st.error("Carica una foto.")
            else:
                est = analyze_food_photo(up.getvalue(), up.type, p_time, p_note)
                st.session_state[f"photo_ai_est_{ds}"] = est

        est = st.session_state.get(f"photo_ai_est_{ds}")
        if est:
            st.info(f"Stima: {kcal_round(est.get('total_calories', 0))} kcal")
            if est.get("notes"):
                st.caption(f"📝 {est.get('notes')}")
            adj_kcal = st.number_input(
                "Kcal (modificabile)", min_value=0, value=int(round(float(est.get("total_calories") or 0))),
                step=10, key=f"photo_ai_adj_{ds}", disabled=is_closed
            )
            adj_desc = st.text_input(
                "Descrizione (modificabile)", value=(est.get("description") or "Pasto (foto)").strip(),
                key=f"photo_ai_desc_{ds}", disabled=is_closed
            )
            if st.button("Salva pasto (foto)", key=f"photo_ai_save_{ds}", disabled=is_closed):
                insert_meal(user_id, ds, p_time.strip(), adj_desc.strip(), float(adj_kcal), json.dumps(est, ensure_ascii=False))
                st.session_state.pop(f"photo_ai_est_{ds}", None)
                st.rerun()

    # Manual
    with tab3:
        man_time = st.text_input("Ora", value="13:00", key=f"man_time_{ds}", disabled=is_closed)
        man_desc = st.text_input("Descrizione", value="", key=f"man_desc_{ds}", disabled=is_closed)
        man_kcal = st.number_input("Kcal", min_value=0, value=0, step=10, key=f"man_kcal_{ds}", disabled=is_closed)
        if st.button("Salva manuale", key=f"man_save_{ds}", disabled=is_closed):
            if not man_desc.strip():
                st.error("Inserisci una descrizione.")
            else:
                insert_meal(user_id, ds, man_time.strip(), man_desc.strip(), float(man_kcal), None)
                st.rerun()
