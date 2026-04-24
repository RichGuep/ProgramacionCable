import streamlit as st
import pandas as pd
import io
import os
import calendar
from datetime import datetime
from logic import load_base, generar_malla_tecnica_completa
from styles import estilo_malla

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    if 'auth' not in st.session_state: st.session_state['auth'] = False

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
                    else: st.error("Acceso denegado")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    df_raw = load_base()
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
        menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"], label_visibility="collapsed")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    if menu == "🏠 Inicio":
        st.markdown(f'<div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;"><h1>Bienvenido Richard Guevara</h1><p>Control Operativo de Planta y Personal - {mes_sel} {ano_sel}</p></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Personal Técnico", "Planta Completa", "Activo")
        c2.metric("Auxiliares", "10/10", "Programados")
        c3.metric("Sincronización", "Sistemas OK", "Hoy")

    elif menu == "📊 Gestión de Mallas":
        if df_raw is None: st.error("No se encontró 'empleados.xlsx'")
        else:
            tab1, tab2 = st.tabs(["Planta Operativa (T1-T3)", "Auxiliares de Abordaje"])
            with tab1:
                col_r = st.columns(3)
                m_req = col_r[0].number_input("Masters x Grupo", 1, 5, 2)
                ta_req = col_r[1].number_input("Tec A x Grupo", 1, 15, 7)
                tb_req = col_r[2].number_input("Tec B x Grupo", 1, 10, 3)
                with st.expander("📅 Grupos y Descansos Legales", expanded=True):
                    n_map, d_map, t_map = {}, {}, {}
                    cg = st.columns(4)
                    for i in range(4):
                        with cg[i]:
                            gn = st.text_input(f"Grupo {i+1}", f"G{i+1}", key=f"gn_{i}")
                            ds = st.selectbox(f"Descanso", DIAS, index=i%7, key=f"gd_{i}")
                            es_d = st.checkbox("Disponibilidad", value=(i==3), key=f"gt_{i}")
                            n_map[f"G{i+1}"] = gn; d_map[gn] = ds; t_map[gn] = "DISP" if es_d else "ROTA"

                if st.button("⚡ GENERAR MALLA TÉCNICA"):
                    df_res = generar_malla_tecnica_completa(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, DIAS)
                    df_piv = df_res.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                    cols_ord = sorted(df_piv.columns, key=lambda x: int(x.split('-')[0]))
                    st.dataframe(df_piv[cols_ord].style.map(estilo_malla), use_container_width=True)

            with tab2:
                st.subheader("Malla Auxiliares (Rotación 10/10)")
                df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
                if not df_ax.empty:
                    if st.button("⚡ GENERAR MALLA AUXILIARES"):
                        num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                        d_info_ax = [{"nom": DIAS[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                        rows_ax = []
                        for d_i in d_info_ax:
                            for _, emp in df_ax.iterrows():
                                t_ax = "T1" if d_i["sem"] % 2 == 0 else "T2"
                                t_f = "DESC. LEY" if d_i["nom"] == "Domingo" else t_ax
                                rows_ax.append({"Empleado": emp['nombre'], "Label": d_i["label"], "Turno": t_f})
                        piv_ax = pd.DataFrame(rows_ax).pivot(index='Empleado', columns='Label', values='Turno')
                        st.dataframe(piv_ax[sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))].style.map(estilo_malla), use_container_width=True)

    elif menu == "👥 Base de Datos":
        st.dataframe(df_raw, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_raw.to_excel(writer, index=False)
        st.download_button("📥 Descargar Base de Datos", data=buffer.getvalue(), file_name="respaldo_base.xlsx")
