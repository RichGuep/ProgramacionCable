import streamlit as st
from main_content import run_app
from styles import apply_global_styles

st.set_page_config(page_title="MovilGo Admin", layout="wide")
apply_global_styles()

if __name__ == "__main__":
    run_app()
