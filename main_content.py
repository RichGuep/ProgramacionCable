import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# Importes de tus módulos locales
from database import read_db, save_db
from logic import load_base, generar_malla_tecnica_pulp
from styles import estilo_malla, get_login_styles

def run_app():
    # --- CONFIGURACIÓN INICIAL ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # --- CARGA DE DATOS DESDE SQLITE ---
    df_users = read_db("usuarios")
    if df_users is None:
        df_users = pd.DataFrame([{"Nombre": "Richard", "Correo": "richard.guevara@greenmovil.com.co", "Rol": "Admin", "Password": "Admin2026"}])
    
    df_raw = read_db("empleados")
    if df_raw is None:
        df_raw = load_base()

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        st.markdown(get_login_styles(), unsafe_allow_html=True)
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH)
            st.markdown('### MovilGo Admin')
            with st.form("Login"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR", use_container_width=True):
                    match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if not match.empty:
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return

    # --- SIDEBAR (NAVEGACIÓN) ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú Principal", opciones, index=opciones.index(st.session_state['menu_actual']))
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- MÓDULO: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación y Control de Mallas")
        tab1, tab2, tab3 = st.tabs(["⚙️ Configuración", "⚡ Vista Previa", "📜 Histórico"])

        with tab1:
            st.subheader("Parámetros del Mes")
            f_mes = st.date_input("Seleccione Mes y Año", datetime(2026, 4, 1))
            
            st.info("Configure los grupos antes de generar.")
            n_map = {"G1": "GRUPO 1", "G2": "GRUPO 2", "G3": "GRUPO 3", "G4": "GRUPO 4"}
            d_map = {"GRUPO 1": "Lunes", "GRUPO 2": "Martes", "GRUPO 3": "Miercoles", "GRUPO 4": "Domingo"}
            t_map = {"GRUPO 1": "ROTA", "GRUPO 2": "ROTA", "GRUPO 3": "ROTA", "GRUPO 4": "DISP"}

            if st.button("🚀 GENERAR MALLA TÉCNICA", use_container_width=True):
                # Generar usando la lógica de logic.py
                malla_gen = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, 2, 7, 3, f_mes.year, f_mes.month, {})
                st.session_state['temp_malla'] = malla_gen
                st.session_state['fecha_malla_ref'] = f_mes
                st.success("Malla generada exitosamente. Revise la pestaña 'Vista Previa'.")

        with tab2:
            # Verificamos que AMBAS llaves existan para evitar el KeyError
            if 'temp_malla' in st.session_state and 'fecha_malla_ref' in st.session_state:
                st.subheader(f"Malla: {st.session_state['fecha_malla_ref'].strftime('%B %Y')}")
                st.dataframe(st.session_state['temp_malla'].style.applymap(estilo_malla), use_container_width=True)
                
                if st.button("💾 GUARDAR ESTA VERSIÓN EN GITHUB", use_container_width=True):
                    malla_json = st.session_state['temp_malla'].to_json(orient='split')
                    nueva_entrada = pd.DataFrame([{
                        "Mes": st.session_state['fecha_malla_ref'].strftime("%B"),
                        "Año": st.session_state['fecha_malla_ref'].year,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json
                    }])
                    
                    df_hist = read_db("historico_mallas")
                    if df_hist is None:
                        df_hist = pd.DataFrame(columns=["Mes", "Año", "Fecha", "Datos_JSON"])
                    
                    if save_db(pd.concat([df_hist, nueva_entrada], ignore_index=True), "historico_mallas"):
                        st.success("✅ Malla guardada y respaldada en GitHub.")
            else:
                st.warning("⚠️ No hay datos generados. Ve a la pestaña '⚙️ Configuración' y presiona '🚀 GENERAR MALLA TÉCNICA'.")

        with tab3:
            st.subheader("Versiones Guardadas")
            df_h = read_db("historico_mallas")
            if df_h is not None and not df_h.empty:
                for i, row in df_h.iterrows():
                    with st.expander(f"📅 {row['Mes']} {row['Año']} - (Guardado: {row['Fecha']})"):
                        if st.button("Cargar esta versión", key=f"btn_{i}"):
                            df_rec = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.session_state['temp_malla'] = df_rec
                            st.info("Versión cargada en 'Vista Previa'.")
            else:
                st.write("No hay registros en el histórico.")

    # --- MÓDULO: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Personal")
        st.dataframe(df_raw, use_container_width=True)
        
        with st.form("registro_tec"):
            st.subheader("Añadir Técnico")
            n = st.text_input("Nombre Completo")
            c = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar Registro"):
                if n:
                    nuevo_personal = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    if save_db(nuevo_personal, "empleados"):
                        st.success(f"Técnico {n} guardado."); st.rerun()
                else:
                    st.error("El nombre es obligatorio.")

    # --- MÓDULO: INICIO ---
    else:
        st.title("🚀 Sistema MovilGo Admin")
        st.markdown(f"**Bienvenido Richard.** Actualmente hay **{len(df_raw)}** técnicos registrados.")
        st.info("Seleccione una opción en el menú lateral para comenzar.")

if __name__ == "__main__":
    run_app()
