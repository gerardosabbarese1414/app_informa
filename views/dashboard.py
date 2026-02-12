# views/dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

from database import conn, init_db


def safe_read_sql(query: str, params=()):
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        return pd.DataFrame()


def _date_range(days: int):
    end = date.today()
    start = end - timedelta(days=days - 1)
    return start, end


def render(user_id: int):
    init_db()

    st.title("Dashboard")

    # -----------------------------
    # Periodo
    # -----------------------------
    period = st.segmented_control(
        "Periodo",
        options=["7 giorni", "30 giorni", "90 giorni"],
        default="30 giorni"
    )
    days = 7 if period == "7 giorni" else 30 if period == "30 giorni" else 90
    d0, d1 = _date_range(days)

    st.caption(f"Mostro dati dal {d0.isoformat()} al {d1.isoformat()}")

    # -----------------------------
    # KPI: giornate chiuse + NET
    # -----------------------------
    # Giorni chiusi nel periodo
    closed_row = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM day_logs
        WHERE user_id = ?
          AND is_closed = 1
          AND date BETWEEN ? AND ?
        """,
        (user_id, str(d0), str(d1))
    ).fetchone()
    closed_days = int(closed_row["n"]) if closed_row and closed_row["n"] is not None else 0

    # NET totale (solo giornate chiuse) nel periodo
    net_row = conn.execute(
        """
        SELECT COALESCE(SUM(ds.net_calories), 0) AS net_sum
        FROM daily_summaries ds
        JOIN day_logs dl
          ON dl.user_id = ds.user_id AND dl.date = ds.date
        WHERE ds.user_id = ?
          AND dl.is_closed = 1
          AND ds.date BETWEEN ? AND ?
        """,
        (user_id, str(d0), str(d1))
    ).fetchone()
    net_sum = float(net_row["net_sum"]) if net_row and net_row["net_sum"] is not None else 0.0

    # Calorie IN/OUT totali (solo giornate chiuse)
    io_row = conn.execute(
        """
        SELECT
          COALESCE(SUM(ds.calories_in), 0)  AS in_sum,
          COALESCE(SUM(ds.calories_out), 0) AS out_sum
        FROM daily_summaries ds
        JOIN day_logs dl
          ON dl.user_id = ds.user_id AND dl.date = ds.date
        WHERE ds.user_id = ?
          AND dl.is_closed = 1
          AND ds.date BETWEEN ? AND ?
        """,
        (user_id, str(d0), str(d1))
    ).fetchone()
    in_sum = float(io_row["in_sum"]) if io_row and io_row["in_sum"] is not None else 0.0
    out_sum = float(io_row["out_sum"]) if io_row and io_row["out_sum"] is not None else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Giornate chiuse", closed_days)
    c2.metric("NET (solo chiuse)", int(round(net_sum)))
    c3.metric("IN / OUT (solo chiuse)", f"{int(round(in_sum))} / {int(round(out_sum))}")

    st.divider()

    # -----------------------------
    # Dataset per grafici
    # -----------------------------
    # Prendo tutte le giornate del periodo con eventuale riepilogo + stato chiusura + peso
    df = safe_read_sql(
        """
        SELECT
          dl.date AS date,
          dl.is_closed AS is_closed,
          dl.morning_weight AS morning_weight,
          COALESCE(ds.calories_in, 0) AS calories_in,
          COALESCE(ds.rest_calories, 0) AS rest_calories,
          COALESCE(ds.workout_calories, 0) AS workout_calories,
          COALESCE(ds.calories_out, 0) AS calories_out,
          COALESCE(ds.net_calories, 0) AS net_calories
        FROM day_logs dl
        LEFT JOIN daily_summaries ds
          ON ds.user_id = dl.user_id AND ds.date = dl.date
        WHERE dl.user_id = ?
          AND dl.date BETWEEN ? AND ?
        ORDER BY dl.date
        """,
        (user_id, str(d0), str(d1))
    )

    # Se day_logs non ha righe (utente nuovo), proviamo a mostrare comunque daily_summaries
    if df.empty:
        df = safe_read_sql(
            """
            SELECT
              ds.date AS date,
              0 AS is_closed,
              NULL AS morning_weight,
              COALESCE(ds.calories_in, 0) AS calories_in,
              COALESCE(ds.rest_calories, 0) AS rest_calories,
              COALESCE(ds.workout_calories, 0) AS workout_calories,
              COALESCE(ds.calories_out, 0) AS calories_out,
              COALESCE(ds.net_calories, 0) AS net_calories
            FROM daily_summaries ds
            WHERE ds.user_id = ?
              AND ds.date BETWEEN ? AND ?
            ORDER BY ds.date
            """,
            (user_id, str(d0), str(d1))
        )

    if df.empty:
        st.info("Non ci sono ancora dati nel periodo selezionato.")
        return

    # parsing date
    df["date"] = pd.to_datetime(df["date"])

    # -----------------------------
    # Grafici
    # -----------------------------
    st.subheader("Andamento")

    # 1) NET (solo chiuse) — ma mostriamo tutte, evidenziando chiuse via filtro
    show_only_closed = st.toggle("Mostra solo giornate chiuse", value=True)
    gdf = df.copy()
    if show_only_closed:
        gdf = gdf[gdf["is_closed"] == 1]

    if gdf.empty:
        st.warning("Nel periodo selezionato non ci sono giornate chiuse.")
    else:
        fig_net = px.line(gdf, x="date", y="net_calories", markers=True, title="NET giornaliero")
        st.plotly_chart(fig_net, use_container_width=True)

        # 2) Calorie IN vs OUT
        fig_io = px.line(
            gdf,
            x="date",
            y=["calories_in", "calories_out"],
            markers=True,
            title="Calorie IN vs OUT"
        )
        st.plotly_chart(fig_io, use_container_width=True)

        # 3) Peso (se presente)
        wdf = gdf.dropna(subset=["morning_weight"]).copy()
        if not wdf.empty:
            fig_w = px.line(wdf, x="date", y="morning_weight", markers=True, title="Peso mattutino")
            st.plotly_chart(fig_w, use_container_width=True)
        else:
            st.caption("Peso mattutino: nessun dato nel periodo (compila 'Peso mattino' nella pagina Giornata).")

    st.divider()

    # -----------------------------
    # Tabella riepilogo (utile debug)
    # -----------------------------
    with st.expander("Dati (debug)"):
        show_cols = [
            "date", "is_closed", "morning_weight",
            "calories_in", "rest_calories", "workout_calories",
            "calories_out", "net_calories"
        ]
        st.dataframe(df[show_cols], use_container_width=True)