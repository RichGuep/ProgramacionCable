import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# Importes de tus otros archivos
from database import read_db, save_db
from logic import load_base, generar_malla_tecnica_pulp
from styles import estilo_malla, get_login_styles

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    # 1. Configuración de estados
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # 2. Carga de datos desde SQLite
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
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH):
                st.image(LOGO_PATH)
            st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            with st.form("Login"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR", use_container_width=True):
                    user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if not user_match.empty:
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
        return

    # --- SIDEBAR ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"]
        st.session_state['menu_actual'] = st.radio("Navegación", opciones, index=opciones.index(st.session_state['menu_actual']))
        
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- VISTA: INICIO ---
    if st.session_state['menu_actual'] == "🏠 Inicio":
        st.title("👋 Panel de Control")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("📊 GESTIÓN DE MALLAS", use_container_width=True):
                st.session_state['menu_actual'] = "📊 Gestión de Mallas"; st.rerun()
        with c2:
            if st.button("👥 BASE DE DATOS", use_container_width=True):
                st.session_state['menu_actual'] = "👥 Base de Datos"; st.rerun()
        with c3:
            if st.button("⚙️ USUARIOS", use_container_width=True):
                st.session_state['menu_actual'] = "⚙️ Usuarios"; st.rerun()

    # --- VISTA: GESTIÓN DE MALLAS ---
    elif st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación de Mallas")
        df_hist = read_db("historico_mallas")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Fecha", "Datos_JSON"])

        tab1, tab2, tab3 = st.tabs(["⚙️ Generar", "⚡ Vista", "📜 Historial"])

        with tab1:
            f_mes = st.date_input("Mes a programar", datetime(2026, 4, 1))
            st.subheader("Configuración de Grupos")
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    n = st.text_input(f"Nombre G{i+1}", f"GRUPO {i+1}", key=f"gn{i}")
                    d = st.selectbox(f"Descanso G{i+1}", DIAS_SEMANA, index=i%7, key=f"gd{i}")
                    disp = st.checkbox(f"Disponible", value=(i==3), key=f"gt{i}")
                    n_map[f"G{i+1}"] = n; d_map[n] = d; t_map[n] = "DISP" if disp else "ROTA"

            if st.button("🚀 CALCULAR MALLA", use_container_width=True):
                # Usamos los parámetros por defecto (2 Masters, 7 Tec A, 3 Tec B)
                st.session_state['temp_malla'] = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, 2, 7, 3, f_mes.year, f_mes.month, {})
                st.success("Malla generada.")

        with tab2:
            if 'temp_malla' in st.session_state:
                st.subheader("⚡ Vista Previa de la Malla")
                st.dataframe(st.session_state['temp_malla'].style.map(estilo_malla), use_container_width=True)
                
                # BOTÓN PARA GUARDAR LA MALLA EN EL HISTÓRICO
                if st.button("💾 GUARDAR ESTA VERSIÓN EN EL HISTÓRICO"):
                    # 1. Convertir la malla (DataFrame) a un formato de texto (JSON)
                    malla_json = st.session_state['temp_malla'].to_json(orient='split')
                    
                    # 2. Crear el registro para la base de datos
                    nueva_fila = pd.DataFrame([{
                        "Mes": f_mes.strftime("%B"),
                        "Año": f_mes.year,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json
                    }])
                    
                    # 3. Leer el histórico actual, sumar la nueva y guardar
                    df_hist_actual = read_db("historico_mallas")
                    if df_hist_actual is None:
                        df_hist_actual = pd.DataFrame(columns=["Mes", "Año", "Fecha", "Datos_JSON"])
                    
                    df_final = pd.concat([df_hist_actual, nueva_fila], ignore_index=True)
                    
                    if save_db(df_final, "historico_mallas"):
                        st.success("✅ Malla guardada en el histórico y sincronizada con GitHub.")
            else:
                st.info("Primero genera una malla en la pestaña 'Configuración'.")

    # --- VISTA: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Personal")
        with st.expander("➕ Agregar Nuevo Técnico"):
            with st.form("add_tec"):
                nom = st.text_input("Nombre Completo")
                car = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
                if st.form_submit_button("GUARDAR EN DB"):
                    if nom:
                        nuevo = pd.concat([df_raw, pd.DataFrame([{"nombre": nom.upper(), "cargo": car, "grupo": "SIN GRUPO"}])], ignore_index=True)
                        if save_db(nuevo, "empleados"):
                            st.success("Técnico registrado"); st.rerun()
        
        st.divider()
        st.dataframe(df_raw, use_container_width=True)
        
        st.subheader("🗑️ Eliminar Registro")
        elim = st.selectbox("Seleccione para borrar:", df_raw['nombre'].tolist() if not df_raw.empty else [], index=None)
        if st.button("❌ ELIMINAR") and elim:
            if save_db(df_raw[df_raw['nombre'] != elim], "empleados"):
                st.warning("Registro eliminado"); st.rerun()

    # --- VISTA: USUARIOS ---
    elif st.session_state['menu_actual'] == "⚙️ Usuarios":
        st.header("⚙️ Usuarios del Sistema")
        st.table(df_users[["Nombre", "Correo", "Rol"]])

if __name__ == "__main__":
    run_app()
