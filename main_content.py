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

    # --- SIDEBAR DINÁMICO ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        st.divider()

        # CONTROL DE VISIBILIDAD: Solo sale si estamos en Gestión de Mallas
        if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
            st.subheader("📅 Periodo a Programar")
            f_inicio = st.date_input("Fecha Inicio", datetime(2026, 4, 1))
            f_fin = st.date_input("Fecha Fin", datetime(2026, 4, 30))
            st.divider()
        else:
            # Fechas por defecto internas para evitar errores de referencia
            f_inicio, f_fin = datetime(2026, 4, 1), datetime(2026, 4, 30)

        # Menú de navegación clásica
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"]
        st.session_state['menu_actual'] = st.radio("Menú de Navegación", opciones, index=opciones.index(st.session_state['menu_actual']))
        
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state['auth'] = False
            st.rerun()

    # --- DISEÑO DE TARJETAS (CSS) ---
    st.markdown("""
        <style>
        .card-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 10px;
        }
        .card {
            background-color: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
            border-left: 8px solid #10b981;
            transition: transform 0.2s;
            cursor: pointer;
        }
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px rgba(0,0,0,0.15);
        }
        </style>
    """, unsafe_allow_html=True)

    # --- VISTA: INICIO (DASHBOARD) ---
    if st.session_state['menu_actual'] == "🏠 Inicio":
        st.title(f"👋 Bienvenido, {st.session_state['rol']}")
        st.write("Seleccione el módulo de gestión técnica:")
        
        st.divider()
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown('<div style="color:#065f46; font-weight:bold; margin-bottom:10px;">OPERACIONES</div>', unsafe_allow_html=True)
            if st.button("📊 GESTIÓN DE MALLAS\n\nProgramación y Turnos", use_container_width=True):
                st.session_state['menu_actual'] = "📊 Gestión de Mallas"
                st.rerun()
                
        with c2:
            st.markdown('<div style="color:#1e40af; font-weight:bold; margin-bottom:10px;">RECURSOS HUMANOS</div>', unsafe_allow_html=True)
            if st.button("👥 BASE DE DATOS\n\nConsulta de Personal", use_container_width=True):
                st.session_state['menu_actual'] = "👥 Base de Datos"
                st.rerun()
        
        with c3:
            st.markdown('<div style="color:#92400e; font-weight:bold; margin-bottom:10px;">SISTEMA</div>', unsafe_allow_html=True)
            if st.button("⚙️ USUARIOS\n\nConfiguración y Roles", use_container_width=True):
                st.session_state['menu_actual'] = "⚙️ Usuarios"
                st.rerun()

        st.divider()
        st.info("**Soporte Técnico Operativo:** richard.guevara@greenmovil.com.co")

    # --- VISTA: GESTIÓN DE MALLAS ---
    elif st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        tab1, tab2, tab3 = st.tabs(["⚙️ Parametrización", "⚡ Vista Previa y Reporte", "📜 Histórico"])

        with tab1:
            st.header("🎮 Centro de Control")
            c_cfg = st.columns(3)
            m_req = c_cfg[0].number_input("Masters", 1, 5, 2)
            ta_req = c_cfg[1].number_input("Tec A", 1, 15, 7)
            tb_req = c_cfg[2].number_input("Tec B", 1, 10, 3)

            st.subheader("Horarios de Operación")
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
                st.success("Malla calculada. Revise la siguiente pestaña.")

        with tab2:
            if 'temp_malla_tec' in st.session_state:
                df_v = st.session_state['temp_malla_tec']
                st.subheader("🔍 Filtros de Reporte")
                
                f_row = st.columns([2, 1, 1])
                with f_row[0]:
                    st.write("**Seleccionar Rango de Fechas:**")
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

                if st.button("💾 GUARDAR EN HISTÓRICO", use_container_width=True):
                    nueva = pd.DataFrame([{"Mes": f_inicio.strftime("%B"), "Año": f_inicio.year, "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Datos_JSON": df_v.to_json(orient='split')}])
                    if guardar_excel_en_github(pd.concat([df_hist, nueva], ignore_index=True), "historico_mallas.xlsx"):
                        st.success("✅ Guardado en GitHub.")
            else:
                st.info("No hay datos generados.")

    # --- OTRAS VISTAS ---
  # --- VISTA: BASE DE DATOS (GESTIÓN DE PERSONAL) ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Personal Operativo")
        
        # 1. Formulario para Nuevo Ingreso
        with st.expander("➕ REGISTRAR NUEVO PERSONAL", expanded=False):
            with st.form("form_nuevo_personal"):
                c1, c2, c3 = st.columns(3)
                nuevo_nombre = c1.text_input("Nombre Completo")
                nuevo_cargo = c2.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B", "AUXILIAR"])
                nuevo_grupo = c3.text_input("Asignar Grupo (Opcional)", "Sin Grupo")
                
                if st.form_submit_button("GUARDAR EN BASE DE DATOS", use_container_width=True):
                    if nuevo_nombre:
                        # Crear nueva fila
                        nueva_data = pd.DataFrame([{
                            "Empleado": nuevo_nombre.upper(),
                            "Cargo": nuevo_cargo,
                            "Grupo": nuevo_grupo.upper()
                        }])
                        
                        # Concatenar con la base actual
                        df_actualizado = pd.concat([df_raw, nueva_data], ignore_index=True)
                        
                        # Guardar en GitHub
                        if guardar_excel_en_github(df_actualizado, "base_personal.xlsx"):
                            st.success(f"✅ {nuevo_nombre} ha sido registrado exitosamente.")
                            st.rerun() # Refrescar para mostrar el cambio en la tabla
                    else:
                        st.error("El nombre es obligatorio.")

        st.divider()

        # 2. Visualización y Edición
        st.subheader("📋 Listado de Personal Activo")
        if df_raw is not None:
            # Añadimos un buscador rápido
            busqueda = st.text_input("🔍 Buscar empleado por nombre...", "")
            df_mostrar = df_raw[df_raw['Empleado'].str.contains(busqueda.upper(), na=False)] if busqueda else df_raw
            
            st.dataframe(df_mostrar, use_container_width=True, height=400)
            
            # Estadísticas rápidas
            st.caption(f"Total personal activo: {len(df_raw)} | Filtro: {len(df_mostrar)}")
        
        st.divider()
        if st.button("⬅️ VOLVER AL INICIO"):
            st.session_state['menu_actual'] = "🏠 Inicio"
            st.rerun()

if __name__ == "__main__":
    run_app()
