import streamlit as st
import traceback

def safe_section(title: str, fn):
    try:
        fn()
    except Exception as e:
        st.error(f"⚠️ Sezione '{title}' in errore: {e}")
        with st.expander("Dettagli tecnici"):
            st.code(traceback.format_exc())
