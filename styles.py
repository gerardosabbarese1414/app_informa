import streamlit as st

def load_styles():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1200px; }
          .stApp { background: radial-gradient(1200px 600px at 20% 0%, rgba(99,102,241,0.18), transparent 60%),
                          radial-gradient(1200px 600px at 80% 10%, rgba(34,197,94,0.12), transparent 55%); }

          .cal-wrap { margin: 0 auto; }
          .cal-head {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 10px;
            margin: 8px 0 8px 0;
          }
          .cal-head div {
            font-weight: 800;
            opacity: 0.75;
            padding: 6px 10px;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 0.06em;
          }

          .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 10px; }

          .cal-cell {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            border-radius: 18px;
            padding: 10px 10px;
            min-height: 128px;
            display: block;
            color: inherit !important;
            text-decoration: none !important;
            transition: transform .06s ease, background .08s ease, border-color .08s ease;
            overflow: hidden;
          }
          .cal-cell:hover {
            transform: translateY(-2px);
            background: rgba(255,255,255,0.06);
            border-color: rgba(255,255,255,0.18);
          }

          .cal-empty {
            border: 1px dashed rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.01);
            border-radius: 18px;
            min-height: 128px;
          }

          .cal-top { display:flex; align-items:center; justify-content:space-between; gap:10px; }
          .cal-daynum { font-weight: 900; font-size: 16px; display:inline-flex; align-items:center; gap:8px; }

          .pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 800;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            opacity: 0.95;
            white-space: nowrap;
          }
          .pill-closed { border-color: rgba(34,197,94,0.25); background: rgba(34,197,94,0.10); }
          .pill-open   { border-color: rgba(148,163,184,0.20); background: rgba(148,163,184,0.08); }

          .mini { margin-top: 8px; display:grid; gap:6px; font-size:12px; line-height:1.2; opacity:0.92; }
          .mini div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

          .badge-ok { color: #22c55e; font-weight: 900; }
          .badge-warn { color: #f59e0b; font-weight: 900; }
          .badge-bad { color: #ef4444; font-weight: 900; }

          .evt {
            padding: 4px 8px;
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            gap: 8px;
          }
          .evt b { font-weight: 800; }
        </style>
        """,
        unsafe_allow_html=True
    )