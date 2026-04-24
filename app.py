import streamlit as st
from main_content import run_app
from styles import apply_global_styles

# Configuración de página (Debe ser la primera instrucción de Streamlit)
st.set_page_config(
    page_title="MovilGo Admin",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Aplicar los estilos globales definidos en styles.py
apply_global_styles()

if __name__ == "__main__":
    run_app()
