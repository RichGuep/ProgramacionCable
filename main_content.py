import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime, timedelta

# IMPORTACIONES (Asegúrate de que load_base esté en database.py para evitar el error anterior)
from database import read_db, save_db, load_base 
from logic import generar_malla_tecnica_pulp
from styles import estilo_malla, get_login_styles

def run_app():
    # --- CONFIGURACIÓN ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # --- CARGA DE DATOS ---
    df_raw = read_db("empleados")
    if df_raw is None:
        df_raw = load_base()

    # --- LOGIN ---
    if not st.session_state['auth']:
        st.markdown(get_login_styles(), unsafe_allow_html=True)
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH)
            st.markdown('### 🔐 MovilGo Admin')
            with st.form("Login"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR", use_container_width=True):
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return

    # --- NAVEGACIÓN ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú", opciones, index=opciones.index(st.session_state['menu_actual']))
        st.divider()
        if st.button("🚪 Salir"):
            st.session_state['auth'] = False
            st.rerun()

    # --- MODULO: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Centro de Control Operativo")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros", "⚡ Vista Horizontal", "📜 Histórico"])

        with tab1:
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                rango = st.date_input("Inicio y Fin", value=(datetime(2026, 4, 1), datetime(2026, 4, 30)))
            
            with c_cupos:
                st.subheader("👥 Cupos y 🕒 Horarios")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                t1_h = c1.text_input("T1", "06:00-14:00")
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                t2_h = c2.text_input("T2", "14:00-22:00")
                b_cupo = c3.number_input("Tec B", 1, 20, 3)
                t3_h = c3.text_input("T3", "22:00-06:00")

            st.divider()
            st.subheader("🛠️ Grupos y Descansos")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nom = st.text_input(f"Nombre", f"GRUPO {i+1}", key=f"gn_{i}")
                    des = st.selectbox(f"Descanso", DIAS_SEMANA, index=i if i<3 else 6, key=f"gd_{i}")
                    n_map[f"G{i+1}"], d_map[nom], t_map[nom] = nom, des, "ROTA"

            if st.button("🚀 GENERAR MALLA OPERATIVA", use_container_width=True):
                if len(rango) == 2:
                    st.session_state['horarios'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}
                    f_i, f_f = rango
                    with st.spinner("Optimizando rotaciones..."):
                        malla_long = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_cupo, a_cupo, b_cupo, f_i.year, f_i.month, {"inicio": f_i, "fin": f_f})
                        if isinstance(malla_long, pd.DataFrame) and not malla_long.empty:
                            st.session_state['temp_malla'] = malla_long
                            st.session_state['rango_ref'] = rango
                            st.success("Malla generada con éxito.")
                        else:
                            st.error("Error: El motor de optimización no devolvió datos válidos.")
                else:
                    st.error("Seleccione un rango válido.")

        with tab2:
            if 'temp_malla' in st.session_state:
                df_long = st.session_state['temp_malla']
                
                # VALIDACIÓN ANTES DEL PIVOTE
                columnas_necesarias = ['Grupo', 'Empleado', 'Cargo', 'Label', 'Final']
                if all(col in df_long.columns for col in columnas_necesarias):
                    # Pivotamos: Empleados filas, Días columnas
                    df_horiz = df_long.pivot_table(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final', aggfunc='first').reset_index()
                    
                    st.subheader("📅 Cronograma de Turnos (Vista Horizontal)")
                    # Cambiamos applymap por map para Pandas moderno
                    st.dataframe(df_horiz.style.map(estilo_malla), use_container_width=True)
                    
                    # Resumen y Guardado...
                    if st.button("💾 GUARDAR EN GITHUB"):
                        # ... lógica de guardado
                        pass
                else:
                    st.error(f"Estructura de datos inválida. Faltan columnas en la malla generada.")
            else:
                st.warning("⚠️ No hay malla generada.")

    # --- MODULO: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)

if __name__ == "__main__":
    run_app()
