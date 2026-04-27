import streamlit as st
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# Importamos las funciones de nuestros otros archivos
from logic import load_base, generar_malla_tecnica_pulp, reconstruir_malla_desde_json
from styles import estilo_malla, estilo_ax, get_login_styles
from github_utils import guardar_excel_en_github, leer_excel_de_github

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    # 1. Inicializar estados de sesión
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'rol' not in st.session_state:
        st.session_state['rol'] = None
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # 2. Cargar Base de Usuarios
    df_users = leer_excel_de_github("usuarios.xlsx")
    if df_users is None:
        df_users = pd.DataFrame(columns=["Nombre", "Correo", "Rol", "Password"])

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        st.markdown(get_login_styles(), unsafe_allow_html=True)
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            st.markdown('<div class="login-container">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): 
                st.image(LOGO_PATH)
            st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
            st.markdown('<div class="brand-subtitle">Gestión de Operaciones Green Móvil</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            with st.form("Login"):
                u = st.text_input("Usuario Corporativo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR AL PANEL", use_container_width=True):
                    user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'], st.session_state['rol'] = True, "Admin"
                        st.rerun()
                    elif not user_match.empty:
                        st.session_state['auth'], st.session_state['rol'] = True, user_match.iloc[0]['Rol']
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas.")
        return

    # --- PANEL DE NAVEGACIÓN (SIDEBAR) ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()

        # SIDEBAR DINÁMICO: Solo muestra fechas si estamos en Gestión de Mallas
        if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
            st.subheader("📅 Periodo de Programación")
            f_inicio = st.date_input("Fecha Inicio", datetime(2026, 4, 1))
            f_fin = st.date_input("Fecha Fin", datetime(2026, 4, 30))
            st.divider()
        else:
            # Valores por defecto para evitar errores en otras vistas
            f_inicio, f_fin = datetime(2026, 4, 1), datetime(2026, 4, 30)

        # Menú de Radio para navegación clásica
        opciones_menu = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"]
        st.session_state['menu_actual'] = st.radio("Menú", opciones_menu, index=opciones_menu.index(st.session_state['menu_actual']))
        
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- VISTA: INICIO (DASHBOARD) ---
    if st.session_state['menu_actual'] == "🏠 Inicio":
        st.markdown(f"# Bienvenido, {st.session_state['rol']}")
        st.write("Seleccione el módulo al que desea acceder:")
        
        st.divider()
        
        # Grid de Tarjetas estilo Botón
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📊 GESTIÓN DE MALLAS\n\nProgramación técnica y auxiliares", use_container_width=True):
                st.session_state['menu_actual'] = "📊 Gestión de Mallas"
                st.rerun()
                
        with col2:
            if st.button("👥 BASE DE DATOS\n\nConsulta de personal activo", use_container_width=True):
                st.session_state['menu_actual'] = "👥 Base de Datos"
                st.rerun()
        
        col3, col4 = st.columns(2)
        with col3:
            if st.button("⚙️ USUARIOS\n\nGestión de accesos y roles", use_container_width=True):
                st.session_state['menu_actual'] = "⚙️ Usuarios"
                st.rerun()
        with col4:
            st.info("**Soporte Técnico:**\n\n richard.guevara@greenmovil.com.co")

    # --- VISTA: GESTIÓN DE MALLAS ---
    elif st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        tab1, tab2, tab3 = st.tabs(["⚙️ Parametrización", "⚡ Vista Previa y Filtros", "📜 Histórico"])

        with tab1:
            st.header("🎮 Centro de Mando")
            c_dot = st.columns(3)
            m_req = c_dot[0].number_input("Masters", 1, 5, 2)
            ta_req = c_dot[1].number_input("Tec A", 1, 15, 7)
            tb_req = c_dot[2].number_input("Tec B", 1, 10, 3)

            st.subheader("Parametrización de Horarios")
            h_cols = st.columns(3)
            dict_horarios = {}
            for i, t_label in enumerate(["T1", "T2", "T3"]):
                with h_cols[i]:
                    ini = st.text_input(f"Inicio {t_label}", "06:00" if i==0 else "14:00" if i==1 else "22:00", key=f"hi_{i}")
                    fin = st.text_input(f"Fin {t_label}", "14:00" if i==0 else "22:00" if i==1 else "06:00", key=f"hf_{i}")
                    dict_horarios[t_label] = {"inicio": ini, "fin": fin}

            if st.button("🚀 GENERAR PROGRAMACIÓN TÉCNICA", use_container_width=True):
                st.session_state['temp_malla_tec'] = generar_malla_tecnica_pulp(
                    df_raw, {}, {}, {}, m_req, ta_req, tb_req, # Usando valores simplificados para el ejemplo
                    f_inicio.year, f_inicio.month, dict_horarios
                )
                st.success("✅ Malla generada.")

        with tab2:
            if 'temp_malla_tec' in st.session_state:
                df_v = st.session_state['temp_malla_tec']
                
                # --- FILTROS POR RANGO DE FECHAS EN VISTA PREVIA ---
                st.subheader("🔍 Filtros de Visualización")
                f_c1, f_c2, f_c3 = st.columns([2, 1, 1])
                
                with f_c1:
                    st.write("**Periodo a consultar:**")
                    r_col1, r_col2 = st.columns(2)
                    v_ini = r_col1.date_input("Desde", f_inicio, key="v_ini")
                    v_fin = r_col2.date_input("Hasta", f_fin, key="v_fin")
                
                grupo_sel = f_c2.selectbox("👥 Filtrar Grupo", ["Todos"] + sorted(df_v['Grupo'].unique().tolist()))
                modo_vista = f_c3.radio("🖼️ Formato", ["Listado Detallado", "Malla General"], horizontal=False)

                st.divider()

                if modo_vista == "Listado Detallado":
                    # Lógica para filtrar por fechas reales
                    df_v['Fecha_DT'] = df_v['Label'].apply(lambda x: datetime(f_inicio.year, f_inicio.month, int(x.split('-')[0])).date())
                    df_res = df_v[(df_v['Fecha_DT'] >= v_ini) & (df_v['Fecha_DT'] <= v_fin)].copy()
                    
                    if grupo_sel != "Todos":
                        df_res = df_res[df_res['Grupo'] == grupo_sel]
                    
                    df_res['Hr. Inicio'] = df_res['Horario'].apply(lambda x: x.split('-')[0] if '-' in str(x) else "---")
                    df_res['Hr. Fin'] = df_res['Horario'].apply(lambda x: x.split('-')[1] if '-' in str(x) else "---")
                    
                    cols_final = ['Fecha_DT', 'Grupo', 'Empleado', 'Cargo', 'Final', 'Hr. Inicio', 'Hr. Fin']
                    st.dataframe(df_res[cols_final].rename(columns={'Fecha_DT': 'Fecha'}), use_container_width=True, height=500)

                elif modo_vista == "Malla General":
                    piv = df_v.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                    st.dataframe(piv.style.map(estilo_malla), use_container_width=True)

                if st.button("💾 GUARDAR EN GITHUB", use_container_width=True):
                    nueva_fila = pd.DataFrame([{
                        "Mes": f_inicio.strftime("%B"), "Año": f_inicio.year, "Tipo": "Técnica",
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Datos_JSON": df_v.to_json(orient='split')
                    }])
                    if guardar_excel_en_github(pd.concat([df_hist, nueva_fila], ignore_index=True), "historico_mallas.xlsx"):
                        st.success("✅ Guardado exitoso.")
            else:
                st.info("No hay datos generados.")

        with tab3:
            st.subheader("Historial")
            # (Lógica de histórico...)

    # --- OTRAS VISTAS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Base de Datos Maestra")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)
            if st.button("⬅️ Volver al Inicio"):
                st.session_state['menu_actual'] = "🏠 Inicio"
                st.rerun()

    elif st.session_state['menu_actual'] == "⚙️ Usuarios":
        st.header("⚙️ Gestión de Usuarios")
        st.table(df_users[["Nombre", "Correo", "Rol"]])
        if st.button("⬅️ Volver al Inicio"):
            st.session_state['menu_actual'] = "🏠 Inicio"
            st.rerun()

if __name__ == "__main__":
    run_app()
