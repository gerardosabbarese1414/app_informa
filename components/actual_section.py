import streamlit as st
import json

from db.repo_meals import list_meals, delete_meal
from db.repo_workouts import list_workouts, delete_workout
from utils import kcal_round

def render(user_id: int, ds: str, is_closed: bool):
    st.subheader("✅ Consuntivo (reale)")

    meals_df = list_meals(user_id, ds)
    workouts_df = list_workouts(user_id, ds)

    c1, c2, c3 = st.columns(3)
    c1.metric("Calorie IN", f"{kcal_round(meals_df['calories'].sum())} kcal" if not meals_df.empty else "0 kcal")
    c2.metric("Calorie OUT (workout)", f"{kcal_round(workouts_df['calories_burned'].sum())} kcal" if not workouts_df.empty else "0 kcal")
    c3.metric("Pasti", f"{len(meals_df)}")

    if not meals_df.empty:
        st.markdown("**Pasti inseriti**")
        for _, r in meals_df.iterrows():
            left, _, right = st.columns([6, 2, 1])
            with left:
                st.write(f"🍽️ {r['time']} — {r['description']}")
                st.caption(f"{kcal_round(r['calories'])} kcal")
                if r.get("raw_json"):
                    try:
                        jj = json.loads(r["raw_json"])
                        if jj.get("notes"):
                            st.caption(f"📝 {jj.get('notes')}")
                    except Exception:
                        pass
            with right:
                if st.button("🗑️", key=f"del_meal_{ds}_{int(r['id'])}", disabled=is_closed):
                    delete_meal(user_id, int(r["id"]))
                    st.rerun()

    if not workouts_df.empty:
        st.markdown("**Allenamenti inseriti**")
        for _, r in workouts_df.iterrows():
            left, _, right = st.columns([6, 2, 1])
            with left:
                st.write(f"🏃 {r['time']} — {r['description']}")
                st.caption(f"{int(r['duration_min'] or 0)} min — {kcal_round(r['calories_burned'])} kcal")
                if r.get("raw_json"):
                    try:
                        jj = json.loads(r["raw_json"])
                        if jj.get("notes"):
                            st.caption(f"📝 {jj.get('notes')}")
                    except Exception:
                        pass
            with right:
                if st.button("🗑️", key=f"del_work_{ds}_{int(r['id'])}", disabled=is_closed):
                    delete_workout(user_id, int(r["id"]))
                    st.rerun()
