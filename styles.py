import streamlit as st

def load_styles():
    st.markdown("""
    <style>
      .block-container { max-width: 1200px; padding-top: 1.2rem; }
      .badge-ok { color: #16a34a; font-weight: 700; }
      .badge-warn { color: #f59e0b; font-weight: 700; }
      .badge-bad { color: #ef4444; font-weight: 700; }
      .small { font-size: 0.9rem; opacity: 0.9; }
    </style>
    """, unsafe_allow_html=True)