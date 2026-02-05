import streamlit as st

def load_styles():
    st.markdown("""
    <style>
    .block-container { padding: 2rem; }
    h1 { color: #2ecc71; }
    </style>
    """, unsafe_allow_html=True)