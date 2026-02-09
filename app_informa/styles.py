import streamlit as st


def load_styles():
    st.markdown("""
    <style>
      .block-container { padding-top: 1rem; padding-bottom: 3rem; }

      /* Calendar month view (Google-ish) */
      .cal-wrap { max-width: 1100px; margin: 0 auto; }
      .cal-head { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; margin: 10px 0 6px 0; }
      .cal-head div { font-weight: 700; opacity: 0.8; text-align: left; padding: 6px 8px; }

      .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
      .cal-cell {
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 14px;
        padding: 10px 10px;
        min-height: 120px;
        background: rgba(255,255,255,0.03);
        transition: transform .06s ease, background .06s ease;
        text-decoration: none !important;
        color: inherit !important;
        display: block;
      }
      .cal-cell:hover { transform: translateY(-1px); background: rgba(255,255,255,0.06); }
      .cal-daynum { font-weight: 800; font-size: 16px; display: flex; align-items: center; gap: 8px; }
      .cal-muted { opacity: 0.40; }

      .cal-badges { margin-top: 8px; display: grid; gap: 6px; }
      .badge-ok { color: #20c997; font-weight: 800; }
      .badge-warn { color: #f59f00; font-weight: 800; }
      .badge-bad { color: #fa5252; font-weight: 800; }

      .mini { font-size: 12px; opacity: 0.9; }
      .mini div { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    </style>
    """, unsafe_allow_html=True)