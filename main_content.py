import streamlit as st
import pandas as pd
import io
import os
import calendar
from datetime import datetime
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state: 
        st.session_state['auth'] = False

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            st.markdown('<div class="login-card">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, width=320)
            st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
            st.markdown('<div class="brand-subtitle">Planificador de Turnos Green Móvil</div>', unsafe_allow_html=True)
            with st.form("Login"):
                u = st.text_input("Usuario Corporativo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR AL PANEL"):
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'] = True
                        st.rerun()
                    else: 
                        st.error("Acceso denegado")
            st.markdown('</div>', unsafe_allow_html=True)
        return # Detiene la ejecución aquí si no está logueado

    # --- PANEL PRINCIPAL (Solo se llega aquí si auth es True) ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # Definición de variables globales del panel
        menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"], label_visibility="collapsed")
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    # --- NAVEGACIÓN ---
    if menu == "🏠 Inicio":
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
                <h1>Bienvenido Richard Guevara</h1>
                <p>Control Operativo de Planta y Personal - {mes_sel} {ano_sel}</p>
            </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Personal Técnico", "Planta Completa", "Activo")
        c2.metric("Auxiliares", "10/10", "Programados")
        c3.metric("Sincronización", "Sistemas OK", "Hoy")

    elif menu == "📊 Gestión de Mallas":
        if df_raw is None: 
            st.error("Error: No se encontró 'empleados.xlsx'")
        else:
            tab1, tab2 = st.tabs(["Planta Operativa (T1-T3)", "Auxiliares de Abordaje"])

            with tab1:
                st.subheader("Configuración de Planta Técnica")
                col_cfg = st.columns(3)
                m_req = col_cfg[0].number_input("Masters x Grupo", 1, 5, 2)
                ta_req = col_cfg[1].number_input("Tec A x Grupo", 1, 15, 7)
                tb_req = col_cfg[2].number_input("Tec B x Grupo", 1, 10, 3)

                with st.expander("📅 Configuración de Grupos Operativos", expanded=True):
                    n_map, d_map, t_map = {}, {}, {}
                    cols = st.columns(4)
                    for i in range(4):
                        with cols[i]:
                            g_id = f"G{i+1}"
                            n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                            d_s = st.selectbox(f"Descanso {g_id}", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                            es_disp = st.checkbox(f"Disponibilidad {g_id}", value=(i==3), key=f"t_b_{i}")
                            n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

                if st.button("⚡ GENERAR MALLA TÉCNICOS/MASTERS"):
                    # Llamada a logic.py con tu lógica original
                    df_f = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num)
                    piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                    cols_ord = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))

                    def estilo_b(v):
                        v = str(v)
                        if 'DESC' in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                        if 'T3' in v: return 'background-color: #263238; color: white; font-weight: bold'
                        if 'T1' in v: return 'background-color: #E3F2FD; color: #1565C0; border: 1px solid #166534'
                        if 'T2' in v: return 'background-color: #FFF3E0; color: #EF6C00; border: 1px solid #0369a1'
                        return 'color: gray; font-style: italic'

                    st.dataframe(piv[cols_ord].style.map(estilo_b), use_container_width=True)

            with tab2:
                st.subheader("Malla Auxiliares de Abordaje")
                with st.expander("📅 Configurar Descansos Auxiliares", expanded=True):
                    aux_n_map, aux_d_map = {}, {}
                    cols_ax = st.columns(5)
                    for i in range(5):
                        with cols_ax[i]:
                            n_eq = st.text_input(f"Equipo {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                            d_eq = st.selectbox(f"Descanso Aux {i+1}", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                            aux_n_map[i] = n_eq; aux_d_map[n_eq] = d_eq

                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    df_res_ax = generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num)
                    if df_res_ax is not None:
                        piv_ax = df_res_ax.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                        cols_ax_ord = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))

                        def estilo_ax(v):
                            v = str(v)
                            if v == "T1": return 'background-color: #dcfce7; color: #166534'
                            if v == "T2": return 'background-color: #e0f2fe; color: #0369a1'
                            if "DESC" in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                            return 'background-color: #f3f4f6; color: #6b7280'

                        st.dataframe(piv_ax[cols_ax_ord].style.map(estilo_ax), use_container_width=True)

    elif menu == "👥 Base de Datos":
        st.header("Base de Datos Maestra")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_raw.to_excel(writer, index=False)
            st.download_button("📥 Descargar Base de Datos", data=buffer.getvalue(), file_name="respaldo_base.xlsx")
