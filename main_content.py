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

    # --- PANEL PRINCIPAL ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        
        st.divider()
        st.subheader("📅 Periodo de Programación")
        
        # Selección por fechas reales (Sustituye Mes/Año)
        f_inicio = st.date_input("Fecha Inicio", datetime(2026, 4, 1))
        f_fin = st.date_input("Fecha Fin", datetime(2026, 4, 30))
        
        # Mantenemos compatibilidad con el histórico guardando el mes predominante
        mes_ref = f_inicio.strftime("%B")
        ano_ref = f_inicio.year

        st.divider()
        menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"])
        
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    # --- GESTIÓN DE MALLAS ---
    if menu == "📊 Gestión de Mallas":
        df_hist = leer_excel_de_github("historico_mallas.xlsx") or pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        tab1, tab2, tab3 = st.tabs(["⚙️ Panel de Parametrización", "⚡ Vista Previa y Filtros", "📜 Histórico"])

        with tab1:
            st.header("🎮 Centro de Mando Operativo")
            
            # 1. Dotación
            st.subheader("1. Dotación Requerida")
            c_dot = st.columns(3)
            m_req = c_dot[0].number_input("Masters", 1, 5, 2)
            ta_req = c_dot[1].number_input("Tec A", 1, 15, 7)
            tb_req = c_dot[2].number_input("Tec B", 1, 10, 3)

            # 2. Horarios Dinámicos
            st.subheader("2. Parametrización de Horarios")
            h1, h2, h3 = st.columns(3)
            dict_horarios = {}
            for i, t_label in enumerate(["T1", "T2", "T3"]):
                with [h1, h2, h3][i]:
                    st.markdown(f"**Turno {t_label}**")
                    ini = st.text_input(f"Inicio {t_label}", "06:00" if i==0 else "14:00" if i==1 else "22:00", key=f"hi_{i}")
                    fin = st.text_input(f"Fin {t_label}", "14:00" if i==0 else "22:00" if i==1 else "06:00", key=f"hf_{i}")
                    dict_horarios[t_label] = {"inicio": ini, "fin": fin}

            # 3. Grupos y Descansos
            st.subheader("3. Configuración de Grupos")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    n_s = st.text_input(f"Nombre G{i+1}", f"GRUPO {i+1}", key=f"gn_{i}")
                    d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"gd_{i}")
                    es_disp = st.checkbox(f"Disponibilidad", value=(i==3), key=f"gt_{i}")
                    n_map[f"G{i+1}"] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("🚀 GENERAR PROGRAMACIÓN TÉCNICA", use_container_width=True):
                # Lógica de empalme simplificada para el rango de fechas
                st.session_state['temp_malla_tec'] = generar_malla_tecnica_pulp(
                    df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, 
                    f_inicio.year, f_inicio.month, dict_horarios
                )
                st.success("✅ Malla generada. Revise la pestaña 'Vista Previa'")

        with tab2:
            if 'temp_malla_tec' in st.session_state:
                df_v = st.session_state['temp_malla_tec']
                
                # --- SISTEMA DE FILTROS AVANZADOS ---
                st.subheader("🔍 Filtros y Visualización")
                f1, f2, f3 = st.columns(3)
                
                dias_disp = sorted(df_v['Label'].unique(), key=lambda x: int(x.split('-')[0]))
                dia_sel = f1.selectbox("📅 Seleccionar Día (Para Listado)", dias_disp)
                
                grupos_disp = ["Todos"] + sorted(df_v['Grupo'].unique().tolist())
                grupo_sel = f2.selectbox("👥 Filtrar por Grupo", grupos_disp)
                
                modo_vista = f3.radio("🖼️ Formato de Vista", ["Listado por Día", "Malla General", "Conteo"], horizontal=False)

                st.divider()

                # --- MODO 1: LISTADO DIARIO DETALLADO (Requerimiento image_a0bfa0.png) ---
                if modo_vista == "Listado por Día":
                    st.markdown(f"### 📋 Personal Programado: {dia_sel}")
                    df_dia = df_v[df_v['Label'] == dia_sel].copy()
                    if grupo_sel != "Todos":
                        df_dia = df_dia[df_dia['Grupo'] == grupo_sel]
                    
                    # Separar columnas de inicio y fin para mayor claridad
                    df_dia['Hr. Inicio'] = df_dia['Horario'].apply(lambda x: x.split('-')[0] if '-' in str(x) else "---")
                    df_dia['Hr. Fin'] = df_dia['Horario'].apply(lambda x: x.split('-')[1] if '-' in str(x) else "---")
                    
                    cols_show = ['Grupo', 'Empleado', 'Cargo', 'Final', 'Hr. Inicio', 'Hr. Fin']
                    st.dataframe(df_dia[cols_show].sort_values('Hr. Inicio'), use_container_width=True, height=450)

                # --- MODO 2: MALLA GENERAL (Vista image_6ba49b.png) ---
                elif modo_vista == "Malla General":
                    df_malla = df_v.copy()
                    if grupo_sel != "Todos":
                        df_malla = df_malla[df_malla['Grupo'] == grupo_sel]
                    
                    piv = df_malla.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                    st.dataframe(piv.style.map(estilo_malla), use_container_width=True)

                # --- MODO 3: CONTEO ---
                else:
                    resumen = df_v.groupby(['Label', 'Final']).size().unstack(fill_value=0)
                    st.dataframe(resumen.T, use_container_width=True)

                if st.button("💾 GUARDAR ESTA VERSIÓN EN GITHUB", use_container_width=True):
                    # Guardamos usando el mes de referencia de la fecha de inicio
                    nueva_fila = pd.DataFrame([{
                        "Mes": mes_ref, "Año": ano_ref, "Tipo": "Técnica",
                        "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "Datos_JSON": df_v.to_json(orient='split')
                    }])
                    df_hist = pd.concat([df_hist, nueva_fila], ignore_index=True)
                    if guardar_excel_en_github(df_hist, "historico_mallas.xlsx"):
                        st.success("✅ Guardado exitoso")
            else:
                st.info("Genere una malla en la pestaña anterior para visualizar filtros.")

        with tab3:
            st.subheader("Historial de Versiones")
            # ... Lógica de histórico igual a la anterior ...

    # --- BASE DE DATOS ---
    elif menu == "👥 Base de Datos":
        st.header("Personal Registrado")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)

    # --- USUARIOS ---
    elif menu == "⚙️ Usuarios":
        st.header("Control de Acceso")
        st.table(df_users[["Nombre", "Correo", "Rol"]])

if __name__ == "__main__":
    run_app()
