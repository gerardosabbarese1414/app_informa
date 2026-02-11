import streamlit as st
import pandas as pd

from db.repo_planned import list_planned, add_planned, delete_planned, mark_done
from db.repo_meals import insert_meal
from db.repo_workouts import insert_workout
from utils import kcal_round


def render(user_id: int, ds: str, is_closed: bool):
    st.subheader("🗓️ Previsto (pianificato)")

    add_col1, add_col2, add_col3, add_col4 = st.columns([1, 1, 2, 2])
    with add_col1:
        p_type = st.selectbox(
            "Tipo",
            ["meal", "workout"],
            format_func=lambda x: "Pasto" if x == "meal" else "Allenamento",
            key=f"ptype_{ds}",
            disabled=is_closed,
        )
    with add_col2:
        p_time = st.text_input("Ora", value="08:00", key=f"ptime_{ds}", disabled=is_closed)
    with add_col3:
        p_title = st.text_input("Titolo", value="", key=f"ptitle_{ds}", disabled=is_closed)
    with add_col4:
        p_notes = st.text_input("Note", value="", key=f"pnotes_{ds}", disabled=is_closed)

    cA, cB, cC = st.columns([1, 1, 2])
    with cA:
        p_kcal = st.number_input(
            "Kcal previste", min_value=0, value=0, step=50, key=f"pkcal_{ds}", disabled=is_closed
        )
    with cB:
        p_dur = st.number_input(
            "Durata (min) (solo workout)",
            min_value=0,
            value=0,
            step=5,
            key=f"pdur_{ds}",
            disabled=is_closed,
        )
    with cC:
        if st.button("➕ Aggiungi al previsto", disabled=is_closed, key=f"addplanned_{ds}"):
            if not p_title.strip():
                st.error("Inserisci un titolo.")
            else:
                add_planned(
                    user_id,
                    ds,
                    time_str=p_time.strip(),
                    typ=p_type,
                    title=p_title.strip(),
                    expected_calories=float(p_kcal) if p_kcal > 0 else None,
                    duration_min=int(p_dur) if (p_type == "workout" and p_dur > 0) else None,
                    notes=p_notes.strip() if p_notes.strip() else None,
                )
                st.rerun()

    planned = list_planned(user_id, ds)

    if planned.empty:
        st.caption("Nessun evento pianificato per questo giorno.")
        return

    for _, r in planned.iterrows():
        left, mid, right = st.columns([6, 2, 2])
        tag = "🍽️" if r["type"] == "meal" else "🏃"
        kcal = f"~{kcal_round(r['expected_calories'])} kcal" if pd.notna(r["expected_calories"]) else ""
        dur = f"{int(r['duration_min'])} min" if pd.notna(r["duration_min"]) else ""
        status = r["status"] or "planned"

        with left:
            st.markdown(f"**{tag} {r['time']} — {r['title']}**  \n{kcal} {dur}  \n`{status}`")
            if r.get("notes"):
                st.caption(r["notes"])

        with mid:
            done = st.checkbox(
                "Fatto",
                value=(status == "done"),
                key=f"done_{ds}_{int(r['id'])}",
                disabled=is_closed,
            )
            if done and status != "done" and not is_closed:
                if r["type"] == "meal":
                    insert_meal(
                        user_id,
                        ds,
                        str(r["time"]),
                        f"[Previsto] {r['title']}",
                        float(r["expected_calories"] or 0),
                        None,
                    )
                else:
                    insert_workout(
                        user_id,
                        ds,
                        str(r["time"]),
                        f"[Previsto] {r['title']}",
                        int(r["duration_min"] or 0),
                        float(r["expected_calories"] or 0),
                        None,
                    )
                mark_done(user_id, int(r["id"]))
                st.rerun()

        with right:
            if st.button("🗑️", key=f"delplanned_{ds}_{int(r['id'])}", disabled=is_closed):
                delete_planned(user_id, int(r["id"]))
                st.rerun()