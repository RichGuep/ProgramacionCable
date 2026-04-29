import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime, timedelta

# Importes de tus módulos locales
from database import read_db, save_db
from logic import load_base, generar_malla_tecnica_pulp
from styles import estilo_malla, get_login_styles

def run_app():
    # --- CONFIGURACIÓN DE INTERFAZ ---
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

    # --- LÓGICA DE LOGIN (Sin cambios) ---
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
        st.header("📊 Programación Operativa de Turnos")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros y Turnos", "⚡ Vista Horizontal y Resumen", "📜 Histórico"])

        with tab1:
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                st.subheader("📅 Período")
                rango = st.date_input("Inicio y Fin", value=(datetime(2026, 4, 1), datetime(2026, 4, 30)))
            
            with c_cupos:
                st.subheader("👥 Cupos y 🕒 Horarios")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                t1_h = c1.text_input("T1 (Mañana)", "06:00-14:00")
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                t2_h = c2.text_input("T2 (Tarde)", "14:00-22:00")
                b_cupo = c3.number_input("Tec B", 1, 20, 3)
                t3_h = c3.text_input("T3 (Noche)", "22:00-06:00")

            st.divider()
            st.subheader("🛠️ Configuración de Grupos")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nom = st.text_input(f"Nombre", f"GRUPO {i+1}", key=f"gn_{i}")
                    des = st.selectbox(f"Descanso", DIAS_SEMANA, index=i if i<3 else 6, key=f"gd_{i}")
                    tip = st.radio(f"Tipo", ["ROTA", "DISP"], index=0 if i<3 else 1, key=f"gt_{i}")
                    # IMPORTANTE: Mapeo correcto para la lógica de optimización
                    n_map[i+1] = nom
                    d_map[nom] = des
                    t_map[nom] = tip

            if st.button("🚀 GENERAR MALLA ÓPTIMA", use_container_width=True):
                if len(rango) == 2:
                    f_i, f_f = rango
                    
                    # 1. PREPARAR DICCIONARIO DE HORARIOS PARA EL MOTOR
                    # Separamos el string "06:00-14:00" en inicio y fin
                    def parse_h(h_str):
                        try:
                            res = h_str.split("-")
                            return {"inicio": res[0].strip(), "fin": res[1].strip()}
                        except: return {"inicio": h_str, "fin": ""}

                    dict_horarios_motor = {
                        "T1": parse_h(t1_h),
                        "T2": parse_h(t2_h),
                        "T3": parse_h(t3_h)
                    }
                    st.session_state['horarios'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}

                    # 2. LLAMADA AL MOTOR OPTIMIZADO
                    with st.spinner("Optimizando descansos y turnos..."):
                        malla_long = generar_malla_tecnica_pulp(
                            df_raw, n_map, d_map, t_map, 
                            m_cupo, a_cupo, b_cupo, 
                            f_i.year, f_i.month, 
                            dict_horarios_motor
                        )
                    
                    if not malla_long.empty:
                        st.session_state['temp_malla'] = malla_long
                        st.session_state['rango_ref'] = rango
                        st.success("✅ Malla generada con descansos compensados automáticamente.")
                    else:
                        st.error("No se pudo generar la malla. Verifique la disponibilidad de personal.")
                else:
                    st.error("Seleccione un rango válido.")

        # --- TAB 2 Y TAB 3 SE MANTIENEN IGUAL (Solo verifica que usen 'Turno/Estado' como columna) ---
        with tab2:
            if 'temp_malla' in st.session_state:
                df_long = st.session_state['temp_malla']
                # Ajustamos el pivot_table para usar 'Turno/Estado' que es lo que devuelve el nuevo motor
                df_horiz = df_long.pivot_table(
                    index=['Grupo', 'Empleado', 'Cargo'], 
                    columns='Dia', 
                    values='Turno/Estado', 
                    aggfunc='first'
                ).reset_index()
                
                st.subheader("🔍 Filtros de Visualización")
                # ... resto de tu código de filtros ...
                st.dataframe(df_horiz.style.map(estilo_malla), use_container_width=True)
                # ... resto de tu código de resumen ...
