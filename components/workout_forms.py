import streamlit as st
import json

from ai import estimate_workout_from_text
from db.repo_workouts import insert_workout
from profile import get_profile
from utils import kcal_round, heuristic_workout_kcal

def render(user_id: int, ds: str, is_closed: bool):
    st.subheader("🏃 Allenamenti (AI o manuale)")

    w_time = st.text_input("Ora", value="19:00", key=f"w_time_{ds}", disabled=is_closed)
    w_text = st.text_area("Descrizione allenamento (libera)", value="", key=f"w_text_{ds}", disabled=is_closed)
    w_dur = st.number_input("Durata (min) (se la sai)", min_value=0, value=0, step=5, key=f"w_dur_{ds}", disabled=is_closed)

    colA, colB = st.columns(2)
    with colA:
        if st.button("Stima workout con AI", key=f"w_ai_btn_{ds}", disabled=is_closed):
            prof = get_profile(user_id) or {}
            est = estimate_workout_from_text(
                w_text,
                float(prof.get("start_weight") or 0) or None,
                float(prof.get("height_cm") or 0) or None,
            )
            st.session_state[f"w_ai_est_{ds}"] = est
    with colB:
        if st.button("Salva workout manuale", key=f"w_man_save_{ds}", disabled=is_closed):
            if not w_text.strip():
                st.error("Inserisci una descrizione.")
            else:
                kcal_burn = float(heuristic_workout_kcal(w_text, int(w_dur or 45)))
                insert_workout(user_id, ds, w_time.strip(), w_text.strip(), int(w_dur or 0), kcal_burn, None)
                st.rerun()

    est = st.session_state.get(f"w_ai_est_{ds}")
    if est:
        st.info(f"Stima: {kcal_round(est.get('calories_burned', 0))} kcal bruciate")
        if est.get("notes"):
            st.caption(f"📝 {est.get('notes')}")
        adj_kcal = st.number_input(
            "Kcal bruciate (modificabile)", min_value=0,
            value=int(round(float(est.get('calories_burned') or 0))), step=10,
            key=f"w_ai_adj_{ds}", disabled=is_closed
        )
        if st.button("Salva workout (AI)", key=f"w_ai_save_{ds}", disabled=is_closed):
            insert_workout(user_id, ds, w_time.strip(), w_text.strip(), int(w_dur or 0), float(adj_kcal), json.dumps(est, ensure_ascii=False))
            st.session_state.pop(f"w_ai_est_{ds}", None)
            st.rerun()
