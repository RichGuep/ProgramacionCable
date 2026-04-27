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
    # --- CONFIGURACIÓN Y ESTADOS ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # --- CARGA DE DATOS (SQLite) ---
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
            st.markdown('### 🔐 Ingreso al Sistema')
            with st.form("Login"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR", use_container_width=True):
                    match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if not match.empty:
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Acceso denegado. Verifique sus credenciales.")
        return

    # --- NAVEGACIÓN LATERAL ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú Principal", opciones, index=opciones.index(st.session_state['menu_actual']))
        st.divider()
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- MÓDULO 1: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación Técnica")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros", "⚡ Vista Previa", "📜 Histórico"])

        with tab1:
            col_f, col_p = st.columns([1, 2])
            with col_f:
                f_mes = st.date_input("Mes de Trabajo", datetime(2026, 4, 1))
            with col_p:
                st.subheader("👥 Cupos Requeridos")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                b_cupo = c3.number_input("Tec B", 1, 20, 3)

            st.divider()
            st.subheader("🛠️ Configuración de Grupos y Descansos")
            n_map, d_map, t_map = {}, {}, {}
            
            # Generar configuración para 4 grupos
            cols_g = st.columns(4)
            config_grupos = [
                {"nombre": "GRUPO 1", "descanso": 0, "tipo": "ROTA"},
                {"nombre": "GRUPO 2", "descanso": 1, "tipo": "ROTA"},
                {"nombre": "GRUPO 3", "descanso": 2, "tipo": "ROTA"},
                {"nombre": "GRUPO 4", "descanso": 6, "tipo": "DISP"}
            ]

            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nombre = st.text_input(f"Nombre", config_grupos[i]["nombre"], key=f"gn_{i}")
                    descanso = st.selectbox(f"Descanso", DIAS_SEMANA, index=config_grupos[i]["descanso"], key=f"gd_{i}")
                    tipo = st.radio(f"Tipo", ["ROTA", "DISP"], index=0 if config_grupos[i]["tipo"] == "ROTA" else 1, key=f"gt_{i}")
                    
                    n_map[f"G{i+1}"] = nombre
                    d_map[nombre] = descanso
                    t_map[nombre] = tipo

            st.divider()
            if st.button("🚀 GENERAR MALLA ÓPTIMA", use_container_width=True):
                with st.spinner("Calculando turnos..."):
                    malla_res = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_cupo, a_cupo, b_cupo, f_mes.year, f_mes.month, {})
                    st.session_state['temp_malla'] = malla_res
                    st.session_state['fecha_malla_ref'] = f_mes
                    st.success("Malla calculada. Por favor, revise la pestaña 'Vista Previa'.")

        with tab2:
            if 'temp_malla' in st.session_state and 'fecha_malla_ref' in st.session_state:
                st.subheader(f"Malla Sugerida: {st.session_state['fecha_malla_ref'].strftime('%B %Y')}")
                st.dataframe(st.session_state['temp_malla'].style.applymap(estilo_malla), use_container_width=True)
                
                if st.button("💾 CONFIRMAR Y GUARDAR EN GITHUB", use_container_width=True):
                    malla_json = st.session_state['temp_malla'].to_json(orient='split')
                    nueva_entrada = pd.DataFrame([{
                        "Mes": st.session_state['fecha_malla_ref'].strftime("%B"),
                        "Año": st.session_state['fecha_malla_ref'].year,
                        "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json
                    }])
                    df_h = read_db("historico_mallas")
                    if df_h is None:
                        df_h = pd.DataFrame(columns=["Mes", "Año", "Fecha", "Datos_JSON"])
                    
                    if save_db(pd.concat([df_h, nueva_entrada], ignore_index=True), "historico_mallas"):
                        st.success("✅ Malla almacenada en el histórico y sincronizada.")
            else:
                st.warning("⚠️ No hay datos generados. Configure los parámetros en la pestaña anterior.")

        with tab3:
            st.subheader("📜 Mallas Anteriores")
            df_hist_full = read_db("historico_mallas")
            if df_hist_full is not None and not df_hist_full.empty:
                for i, row in df_hist_full.iterrows():
                    with st.expander(f"📅 {row['Mes']} {row['Año']} - (Guardado: {row['Fecha']})"):
                        if st.button("Cargar versión", key=f"v_{i}"):
                            df_recup = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.session_state['temp_malla'] = df_recup
                            st.info("Versión cargada. Ver en la pestaña 'Vista Previa'.")
            else:
                st.info("El histórico está vacío.")

    # --- MÓDULO 2: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)
        
        with st.form("new_tech"):
            st.subheader("➕ Registrar Nuevo Personal")
            n = st.text_input("Nombre y Apellidos")
            c = st.selectbox("Categoría", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar en Base de Datos"):
                if n:
                    nuevo_personal = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    if save_db(nuevo_personal, "empleados"):
                        st.success(f"Técnico {n} registrado con éxito."); st.rerun()
                else:
                    st.error("Debe ingresar un nombre válido.")

    # --- MÓDULO 3: INICIO ---
    else:
        st.title("🚀 MovilGo Admin")
        st.markdown(f"### Bienvenida, Richard.")
        st.write(f"Estado de la base de datos: **{len(df_raw)} técnicos activos.**")
        st.info("Seleccione 'Gestión de Mallas' para programar el mes o 'Base de Datos' para editar el personal.")

if __name__ == "__main__":
    run_app()
