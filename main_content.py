import streamlit as st
import pandas as pd
import io, os, json
from datetime import datetime
from github_utils import guardar_excel_en_github, leer_excel_de_github
from logic import load_base, generar_malla_tecnica_pulp
from styles import estilo_malla

def run_app():
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    if 'auth' not in st.session_state: st.session_state['auth'] = False

    df_users = leer_excel_de_github("usuarios.xlsx") or pd.DataFrame(columns=["Nombre", "Correo", "Rol", "Password"])

    # --- LOGIN ---
    if not st.session_state['auth']:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                if (u == "richard.guevara@greenmovil.com.co" and p == "Admin2026") or not match.empty:
                    st.session_state['auth'] = True
                    st.session_state['rol'] = "Admin" if u.startswith("richard") else match.iloc[0]['Rol']
                    st.rerun()
        return

    df_raw = load_base()
    with st.sidebar:
        menu = st.radio("Menú", ["📊 Gestión de Mallas", "👥 Usuarios", "📂 Base de Datos"])
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        if st.button("Cerrar Sesión"): st.session_state['auth'] = False; st.rerun()

    if menu == "📊 Gestión de Mallas":
        df_hist = leer_excel_de_github("historico_mallas.xlsx") or pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])
        tab1, tab2 = st.tabs(["⚡ Generador", "📜 Histórico"])

        with tab1:
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    n = st.text_input(f"G{i+1}", f"GRUPO {i+1}", key=f"n{i}")
                    d = st.selectbox(f"Descanso", DIAS_SEMANA, index=i%7, key=f"d{i}")
                    t = st.checkbox("Disp", value=(i==3), key=f"t{i}")
                    n_map[f"G{i+1}"], d_map[n], t_map[n] = n, d, ("DISP" if t else "ROTA")

            if st.button("GENERAR MALLA"):
                # --- BUSCAR EMPALME ---
                idx = meses.index(mes_sel)
                m_ant, a_ant = (meses[idx-1], ano_sel) if idx > 0 else (meses[11], ano_sel-1)
                estado_previo = None
                pasado = df_hist[(df_hist['Mes'] == m_ant) & (df_hist['Año'] == a_ant)]
                if not pasado.empty:
                    try:
                        m_old = pd.read_json(io.StringIO(pasado.iloc[0]['Datos_JSON']))
                        u_col = sorted([c for c in m_old.columns if '-' in str(c)], key=lambda x: int(str(x).split('-')[0]))[-1]
                        estado_previo = m_old.set_index('Grupo')[u_col].to_dict()
                        st.info(f"🔄 Empalme aplicado de {m_ant}")
                    except: pass
                
                st.session_state['m_temp'] = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, 2, 7, 3, ano_sel, idx+1, estado_previo)

            if 'm_temp' in st.session_state:
                res = st.session_state['m_temp']
                piv = res.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.dataframe(piv.style.map(estilo_malla), use_container_width=True)
                
                st.divider()
                existe = not df_hist[(df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel)].empty
                confirmar = st.checkbox("⚠️ Reemplazar malla existente?") if existe else True
                
                if st.button("💾 GUARDAR"):
                    if confirmar:
                        df_hist = df_hist[~((df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel))]
                        new_row = pd.DataFrame([{"Mes": mes_sel, "Año": ano_sel, "Tipo": "Técnica", "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Datos_JSON": res.to_json()}])
                        df_hist = pd.concat([df_hist, new_row], ignore_index=True)
                        if guardar_excel_en_github(df_hist, "historico_mallas.xlsx"):
                            st.success("Sincronizado!"); st.balloons()

        with tab2:
            if not df_hist.empty:
                sel = st.selectbox("Versión", range(len(df_hist)), format_func=lambda x: f"{df_hist.iloc[x]['Mes']} {df_hist.iloc[x]['Año']}")
                if st.button("Visualizar"):
                    try:
                        m_rec = pd.read_json(io.StringIO(df_hist.iloc[sel]['Datos_JSON']))
                        st.dataframe(m_rec.style.map(estilo_malla), use_container_width=True)
                    except: st.error("Error al cargar histórico")
