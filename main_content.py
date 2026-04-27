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

    # --- PANEL DE DATOS BASE ---
    df_raw = load_base() # Carga empleados.xlsx desde GitHub vía logic.py

    # --- SIDEBAR DINÁMICO ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()

        # Mostrar fechas SOLO en Gestión de Mallas
        if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
            st.subheader("📅 Periodo a Programar")
            f_inicio = st.date_input("Fecha Inicio", datetime(2026, 4, 1))
            f_fin = st.date_input("Fecha Fin", datetime(2026, 4, 30))
            st.divider()
        else:
            f_inicio, f_fin = datetime(2026, 4, 1), datetime(2026, 4, 30)

        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"]
        st.session_state['menu_actual'] = st.radio("Navegación", opciones, index=opciones.index(st.session_state['menu_actual']))
        
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- VISTA: INICIO (DASHBOARD) ---
    if st.session_state['menu_actual'] == "🏠 Inicio":
        st.title(f"👋 Bienvenido, {st.session_state['rol']}")
        st.write("Seleccione un módulo para comenzar:")
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown('<p style="color:#059669; font-weight:bold;">OPERACIONES</p>', unsafe_allow_html=True)
            if st.button("📊 GESTIÓN DE MALLAS\n\nTurnos y Cobertura", use_container_width=True):
                st.session_state['menu_actual'] = "📊 Gestión de Mallas"
                st.rerun()
        with c2:
            st.markdown('<p style="color:#2563eb; font-weight:bold;">RECURSOS</p>', unsafe_allow_html=True)
            if st.button("👥 BASE DE DATOS\n\nAltas/Bajas Personal", use_container_width=True):
                st.session_state['menu_actual'] = "👥 Base de Datos"
                st.rerun()
        with c3:
            st.markdown('<p style="color:#d97706; font-weight:bold;">CONTROL</p>', unsafe_allow_html=True)
            if st.button("⚙️ USUARIOS\n\nSeguridad y Accesos", use_container_width=True):
                st.session_state['menu_actual'] = "⚙️ Usuarios"
                st.rerun()

    # --- VISTA: GESTIÓN DE MALLAS ---
    elif st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        tab1, tab2, tab3 = st.tabs(["⚙️ Parametrización", "⚡ Vista Previa y Reporte", "📜 Histórico"])

        with tab1:
            st.header("🎮 Parámetros de Programación")
            c_cfg = st.columns(3)
            m_req = c_cfg[0].number_input("Masters Requeridos", 1, 5, 2)
            ta_req = c_cfg[1].number_input("Técnicos A", 1, 15, 7)
            tb_req = c_cfg[2].number_input("Técnicos B", 1, 10, 3)

            st.subheader("Configuración de Horarios")
            h_cols = st.columns(3)
            dict_h = {}
            for i, t in enumerate(["T1", "T2", "T3"]):
                with h_cols[i]:
                    ini = st.text_input(f"Inicio {t}", "06:00" if i==0 else "14:00" if i==1 else "22:00", key=f"hi_{i}")
                    fin = st.text_input(f"Fin {t}", "14:00" if i==0 else "22:00" if i==1 else "06:00", key=f"hf_{i}")
                    dict_h[t] = {"inicio": ini, "fin": fin}

            if st.button("🚀 GENERAR MALLA TÉCNICA", use_container_width=True):
                st.session_state['temp_malla_tec'] = generar_malla_tecnica_pulp(
                    df_raw, {}, {}, {}, m_req, ta_req, tb_req, 
                    f_inicio.year, f_inicio.month, dict_h
                )
                st.success("✅ Malla generada con éxito.")

        with tab2:
            if 'temp_malla_tec' in st.session_state:
                df_v = st.session_state['temp_malla_tec']
                st.subheader("🔍 Filtros de Visualización")
                
                f_row = st.columns([2, 1, 1])
                with f_row[0]:
                    st.write("**Rango de Fechas para Listado:**")
                    r1, r2 = st.columns(2)
                    v_ini = r1.date_input("Desde", f_inicio, key="v_ini")
                    v_fin = r2.date_input("Hasta", f_fin, key="v_fin")
                
                g_sel = f_row[1].selectbox("Grupo", ["Todos"] + sorted(df_v['Grupo'].unique().tolist()))
                modo = f_row[2].radio("Formato", ["Listado Detallado", "Malla Visual"])

                st.divider()

                if modo == "Listado Detallado":
                    df_v['Fecha_DT'] = df_v['Label'].apply(lambda x: datetime(f_inicio.year, f_inicio.month, int(x.split('-')[0])).date())
                    df_res = df_v[(df_v['Fecha_DT'] >= v_ini) & (df_v['Fecha_DT'] <= v_fin)].copy()
                    if g_sel != "Todos": df_res = df_res[df_res['Grupo'] == g_sel]
                    
                    df_res['Hr. Inicio'] = df_res['Horario'].apply(lambda x: x.split('-')[0] if '-' in str(x) else "---")
                    df_res['Hr. Fin'] = df_res['Horario'].apply(lambda x: x.split('-')[1] if '-' in str(x) else "---")
                    
                    st.dataframe(df_res[['Fecha_DT', 'Grupo', 'Empleado', 'Cargo', 'Final', 'Hr. Inicio', 'Hr. Fin']].rename(columns={'Fecha_DT': 'Fecha'}), use_container_width=True)
                else:
                    st.dataframe(df_v.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final').style.map(estilo_malla), use_container_width=True)

                if st.button("💾 GUARDAR VERSIÓN EN GITHUB", use_container_width=True):
                    nueva = pd.DataFrame([{"Mes": f_inicio.strftime("%B"), "Año": f_inicio.year, "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Datos_JSON": df_v.to_json(orient='split')}])
                    if guardar_excel_en_github(pd.concat([df_hist, nueva], ignore_index=True), "historico_mallas.xlsx"):
                        st.success("✅ Guardado en Histórico.")
            else:
                st.info("No hay datos generados aún.")

        with tab3:
            st.subheader("📜 Historial de Programaciones")
            if not df_hist.empty:
                st.dataframe(df_hist[["Mes", "Año", "Fecha"]], use_container_width=True)

    # --- VISTA: BASE DE DATOS (ALTAS/BAJAS) ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Personal")
        
        # 1. Registrar Nuevo
        with st.expander("➕ REGISTRAR NUEVO EMPLEADO", expanded=False):
            with st.form("form_registro", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                nom = c1.text_input("Nombre Completo")
                car = c2.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B", "AUXILIAR"])
                gru = c3.text_input("Grupo (Opcional)", "SIN GRUPO")
                if st.form_submit_button("GUARDAR EN GITHUB"):
                    if nom:
                        df_new = pd.concat([df_raw, pd.DataFrame([{"nombre": nom.upper(), "cargo": car, "grupo": gru.upper()}])], ignore_index=True)
                        if guardar_excel_en_github(df_new, "empleados.xlsx"):
                            st.success(f"{nom} registrado."); st.rerun()
                    else: st.error("Falta el nombre.")

        st.divider()

        # 2. Listado y Eliminación
        st.subheader("📋 Personal Activo")
        if df_raw is not None and not df_raw.empty:
            bus = st.text_input("🔍 Buscar por nombre...").upper()
            df_f = df_raw[df_raw['nombre'].str.contains(bus, na=False)] if bus else df_raw
            st.dataframe(df_f, use_container_width=True, height=300)
            
            st.markdown("---")
            st.subheader("🗑️ Dar de Baja")
            col_sel, col_btn = st.columns([3, 1])
            elim = col_sel.selectbox("Seleccione para eliminar:", df_raw['nombre'].tolist(), index=None)
            if col_btn.button("❌ ELIMINAR", use_container_width=True):
                if elim:
                    if guardar_excel_en_github(df_raw[df_raw['nombre'] != elim], "empleados.xlsx"):
                        st.warning(f"{elim} eliminado."); st.rerun()
        
        if st.button("⬅️ VOLVER AL INICIO"):
            st.session_state['menu_actual'] = "🏠 Inicio"; st.rerun()

    # --- VISTA: USUARIOS ---
    elif st.session_state['menu_actual'] == "⚙️ Usuarios":
        st.header("⚙️ Configuración de Usuarios")
        st.table(df_users[["Nombre", "Correo", "Rol"]])
        if st.button("⬅️ VOLVER AL INICIO"):
            st.session_state['menu_actual'] = "🏠 Inicio"; st.rerun()

if __name__ == "__main__":
    run_app()
