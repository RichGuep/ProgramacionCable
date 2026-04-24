import streamlit as st
import os
import io
import pandas as pd
from datetime import datetime
from styles import apply_custom_styles, estilo_malla
from logic import load_base, generar_malla_tecnica

# 1. Configuración Inicial
apply_custom_styles()
LOGO_PATH = "MovilGo.png"
DIAS_SEM = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

# 2. Manejo de Autenticación
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=320)
        st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# 3. Sidebar y Navegación
df_raw = load_base()
with st.sidebar:
    if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
    menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"])
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    if st.button("Cerrar Sesión"):
        st.session_state['auth'] = False
        st.rerun()

# 4. Enrutamiento de Módulos
if menu == "🏠 Inicio":
    st.title(f"Panel de Control - {mes_sel} {ano_sel}")
    # ... resto del código de inicio ...

elif menu == "📊 Gestión de Mallas":
    if df_raw is not None:
        # Aquí llamas a generar_malla_tecnica de logic.py
        # Y aplicas estilo_malla de styles.py
        pass

elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.dataframe(df_raw, use_container_width=True)
