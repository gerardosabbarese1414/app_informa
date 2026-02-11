import streamlit as st


def load_styles():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1rem; }

          .badge-ok   { color:#0f5132; background:#d1e7dd; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }
          .badge-warn { color:#664d03; background:#fff3cd; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }
          .badge-bad  { color:#842029; background:#f8d7da; padding:2px 8px; border-radius:999px; font-size:12px; display:inline-block; }

          .cal-wrap { width:100%; }
          .cal-head { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; margin:8px 0 10px 0; }
          .cal-head div { font-weight:800; opacity:.85; padding-left:6px; }

          .cal-grid { display:grid; grid-template-columns:repeat(7,1fr); gap:8px; width:100%; }

          a.cal-cell{
            display:block; min-height:112px;
            border:1px solid rgba(120,120,120,.18);
            border-radius:14px;
            padding:10px 10px 8px 10px;
            text-decoration:none !important;
            color:inherit !important;
            background:rgba(255,255,255,.55);
            transition:transform .07s ease, box-shadow .07s ease, border-color .07s ease;
          }
          a.cal-cell:hover{
            transform:translateY(-1px);
            border-color:rgba(100,100,100,.35);
            box-shadow:0 6px 20px rgba(0,0,0,.08);
          }
          .cal-empty{
            min-height:112px;
            border-radius:14px;
            border:1px dashed rgba(120,120,120,.18);
            background:rgba(0,0,0,.02);
          }
          .cal-top{ display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
          .cal-daynum{ font-weight:900; font-size:16px; }
          .cal-dot{ font-size:12px; opacity:.8; }

          .cal-meta{ font-size:12px; opacity:.88; line-height:1.25; }
          .cal-mini{ margin-top:6px; font-size:12px; opacity:.92; }
          .cal-mini div{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

          .cal-today{ outline:2px solid rgba(33,150,243,.35); outline-offset:2px; }

          @media (max-width:900px){
            a.cal-cell, .cal-empty{ min-height:90px; padding:8px; border-radius:12px; }
            .cal-daynum{ font-size:15px; }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )