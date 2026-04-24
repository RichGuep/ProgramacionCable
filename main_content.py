import streamlit as st
import pandas as pd
import io, os, calendar
from datetime import datetime
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool
from styles import estilo_malla, estilo_ax
from github_utils import guardar_excel_en_github

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state: st.session_state['auth'] = False

    # Cargar Usuarios
    if os.path.exists("usuarios.xlsx"): df_users = pd.read_excel("usuarios.xlsx")
    else: df_users = pd.DataFrame(columns=["Nombre", "Correo", "Rol", "Password"])

    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            st.markdown('<div class="login-card">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=320)
            st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
            with st.form("Login"):
                u = st.text_input("Usuario Corporativo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026": # SuperAdmin
                        st.session_state['auth'], st.session_state['rol'] = True, "Admin"
                        st.rerun()
                    elif not user_match.empty:
                        st.session_state['auth'], st.session_state['rol'] = True, user_match.iloc[0]['Rol']
                        st.rerun()
                    else: st.error("Acceso denegado")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    df_raw = load_base()
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
        menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos", "⚙️ Usuarios"], label_visibility="collapsed")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    if menu == "🏠 Inicio":
        st.markdown(f'<div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;"><h1>Bienvenido Richard Guevara</h1><p>Control Operativo de Planta y Personal - {mes_sel} {ano_sel}</p></div>', unsafe_allow_html=True)
    
    elif menu == "📊 Gestión de Mallas":
        t1, t2 = st.tabs(["Técnicos", "Auxiliares"])
        with t1:
            m_req = st.number_input("Masters", 1, 5, 2); ta_req = st.number_input("Tec A", 1, 15, 7); tb_req = st.number_input("Tec B", 1, 10, 3)
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    n = st.text_input(f"G{i+1}", f"GRUPO {i+1}", key=f"n{i}")
                    d = st.selectbox(f"Descanso", DIAS_SEMANA, index=i%7, key=f"d{i}")
                    t = st.checkbox(f"Disp", value=(i==3), key=f"t{i}")
                    n_map[f"G{i+1}"], d_map[n], t_map[n] = n, d, ("DISP" if t else "ROTA")
            if st.button("Generar Malla Técnica"):
                df_res = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num)
                piv = df_res.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.dataframe(piv[sorted(piv.columns, key=lambda x: int(x.split('-')[0]))].style.map(estilo_malla), use_container_width=True)
        with t2:
            aux_n_map, aux_d_map = {}, {}
            cols_ax = st.columns(5)
            for i in range(5):
                with cols_ax[i]:
                    n = st.text_input(f"Equipo {i+1}", f"EQ-{chr(65+i)}", key=f"axn{i}")
                    d = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"axd{i}")
                    aux_n_map[i], aux_d_map[n] = n, d
            if st.button("Generar Malla Auxiliares"):
                df_res_ax = generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num)
                piv_ax = df_res_ax.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                st.dataframe(piv_ax[sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))].style.map(estilo_ax), use_container_width=True)

    elif menu == "⚙️ Usuarios":
        if st.session_state['rol'] != "Admin": st.error("No tienes permisos"); return
        nom = st.text_input("Nombre"); cor = st.text_input("Correo"); rol = st.selectbox("Rol", ["Admin", "Planificador", "Visualizador"]); pwd = st.text_input("PWD", type="password")
        if st.form_submit_button("Registrar"):
            nuevo = pd.DataFrame([[nom, cor, rol, pwd]], columns=df_users.columns)
            df_users = pd.concat([df_users, nuevo], ignore_index=True)
            if guardar_excel_en_github(df_users, "usuarios.xlsx"): st.success("Sincronizado"); st.rerun()
