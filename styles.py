import streamlit as st


def load_styles():
    st.markdown(
        """
        <style>
          /* Riduce la banda/blank in alto */
          .block-container { padding-top: 0.35rem; }
          [data-testid="stHeader"] { background: transparent; }
          [data-testid="stHeader"]::after { content: none; }
          [data-testid="stToolbar"] { right: 0.5rem; }

          /* Badge */
          .badge-ok   { color:#0f5132; background:#d1e7dd; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }
          .badge-warn { color:#664d03; background:#fff3cd; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }
          .badge-bad  { color:#842029; background:#f8d7da; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }

          /* -------------------------
             CALENDARIO: bottoni "card"
             ------------------------- */
          .cal-grid-scope .stButton > button {
            width: 100%;
            min-height: 118px;
            border-radius: 14px;
            border: 1px solid rgba(120,120,120,.18);
            background: rgba(255,255,255,.55);
            text-align: left;
            padding: 10px 10px;
            line-height: 1.2;
            white-space: pre-line;   /* permette i \n */
          }

          .cal-grid-scope .stButton > button:hover {
            border-color: rgba(33,150,243,.35);
          }

          /* celle vuote (disabilitate) */
          .cal-grid-scope .stButton > button:disabled {
            background: rgba(0,0,0,.02);
            border-style: dashed;
            color: rgba(0,0,0,.0);
          }

          /* testo interno */
          .cal-cell-title { font-weight: 900; font-size: 16px; }
          .cal-cell-meta  { font-size: 12px; opacity: .88; margin-top: 6px; }

        </style>
        """,
        unsafe_allow_html=True,
    )