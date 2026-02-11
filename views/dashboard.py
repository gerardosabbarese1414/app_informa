import streamlit as st
import plotly.express as px

from db.common import safe_read_sql
from utils import kcal_round

def render(user_id: int):
    st.header("📊 Dashboard")

    weights = safe_read_sql(
        "SELECT date, morning_weight as weight FROM day_logs WHERE user_id=? AND morning_weight IS NOT NULL ORDER BY date",
        (user_id,)
    )
    sums = safe_read_sql(
        "SELECT date, calories_in, calories_out, net_calories FROM daily_summaries WHERE user_id=? ORDER BY date",
        (user_id,)
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Peso ultimo", f"{weights.iloc[-1]['weight']:.1f} kg" if not weights.empty else "—")
    c2.metric("NET ultimo giorno", f"{kcal_round(sums.iloc[-1]['net_calories'])} kcal" if not sums.empty else "—")
    c3.metric("Giorni chiusi", f"{len(sums)}")

    if not weights.empty:
        st.plotly_chart(px.line(weights, x="date", y="weight", title="Peso nel tempo"), use_container_width=True)

    if not sums.empty:
        st.plotly_chart(
            px.bar(sums.tail(30), x="date", y=["calories_in", "calories_out"], barmode="group",
                title="Calorie IN/OUT (ultimi 30 giorni)"),
            use_container_width=True
        )
        st.plotly_chart(px.line(sums.tail(30), x="date", y="net_calories", title="NET (ultimi 30 giorni)"),
                        use_container_width=True)
