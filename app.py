import streamlit as st
from styles import apply_custom_styles
from main_content import run_app # Aquí es donde estará tu menú

# 1. Aplicamos el diseño
apply_custom_styles()

# 2. Corremos la aplicación
if __name__ == "__main__":
    run_app()
