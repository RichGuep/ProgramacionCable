import streamlit as st
import pandas as pd
import io
import os
import json
from datetime import datetime

# Importamos las funciones de nuestros otros archivos
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool, reconstruir_malla_desde_json
from styles import estilo_malla, estilo_ax
from github_utils import guardar_excel_en_github, leer_excel_de_github

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    # 1. Inicializar estados de sesión
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'rol' not in st.session_state:
        st.session_state['rol'] = None

    # 2. Cargar Base de Usuarios desde GitHub
    df_users = leer_excel_de_github("usuarios.xlsx")
    if df_users is None:
        df_users = pd.DataFrame(columns=["Nombre", "Correo", "Rol", "Password"])

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            st.markdown('<div class="login-card">', unsafe_allow_html=True)
            if os.path.exists(LOGO_PATH): 
                st.image(LOGO_PATH, width=320)
            st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
            
            with st.form("Login"):
                u = st.text_input("Usuario Corporativo")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR AL PANEL"):
                    user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'], st.session_state['rol'] = True, "Admin"
                        st.rerun()
                    elif not user_match.empty:
                        st.session_state['auth'] = True
                        st.session_state['rol'] = user_match.iloc[0]['Rol']
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas.")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # --- PANEL PRINCIPAL ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        
        st.divider()
        st.subheader("🗓️ Periodo a Programar")
        alcance = st.selectbox("Alcance", ["Mes Completo", "1 Semana", "2 Semanas"])
        
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        
        semana_inicio = 1
        if alcance != "Mes Completo":
            semana_inicio = st.number_input("Desde la Semana #", 1, 5, 1)

        mes_num = meses.index(mes_sel) + 1
        
        st.divider()
        menu_options = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        if st.session_state['rol'] == "Admin":
            menu_options.append("⚙️ Usuarios")
        menu = st.radio("Menú", menu_options)
        
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    # --- MÓDULO GESTIÓN DE MALLAS ---
    if menu == "📊 Gestión de Mallas":
        # Cargamos el histórico con blindaje de columnas
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Alcance", "Fecha", "Datos_JSON"])
        else:
            # Si el archivo existe pero no tiene la columna Alcance, la creamos
            if 'Alcance' not in df_hist.columns:
                df_hist['Alcance'] = "Mes Completo"

        tab1, tab2, tab3 = st.tabs(["⚡ Generador Técnicos", "⚡ Generador Auxiliares", "📜 Histórico"])

        with tab1:
            st.subheader(f"Configuración Planta Técnica ({alcance})")
            c_cfg = st.columns(3)
            m_req = c_cfg[0].number_input("Masters", 1, 5, 2)
            ta_req = c_cfg[1].number_input("Tec A", 1, 15, 7)
            tb_req = c_cfg[2].number_input("Tec B", 1, 10, 3)

            with st.expander("📅 Parámetros de Grupos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cols = st.columns(4)
                for i in range(4):
                    with cols[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"tec_n_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"tec_d_{i}")
                        es_disp = st.checkbox(f"Disponible", value=(i==3), key=f"tec_t_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR PROGRAMACIÓN TÉCNICA"):
                # Buscar último estado guardado para empalme
                estado_previo = None
                if not df_hist.empty:
                    pasado = df_hist[(df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Tipo'] == "Técnica")]
                    if not pasado.empty:
                        m_ant = reconstruir_malla_desde_json(pasado.iloc[-1]['Datos_JSON'])
                        if m_ant is not None:
                            cols_d = [c for c in m_ant.columns if '-' in str(c)]
                            ult_col = sorted(cols_d, key=lambda x: int(str(x).split('-')[0]))[-1]
                            estado_previo = m_ant.set_index('Grupo')[ult_col].to_dict()
                            st.info(f"🔄 Empalme aplicado del registro guardado.")

                st.session_state['temp_malla_tec'] = generar_malla_tecnica_pulp(
                    df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, 
                    ano_sel, mes_num, alcance=alcance, semana_inicio=semana_inicio, estado_anterior=estado_previo
                )

            if 'temp_malla_tec' in st.session_state:
                df_v = st.session_state['temp_malla_tec']
                piv = df_v.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.dataframe(piv[sorted(piv.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_malla), use_container_width=True)
                
                st.divider()
                # ALERTA DE REEMPLAZO BLINDADA
                existe = not df_hist[(df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Alcance'] == alcance)].empty
                confirmar = st.checkbox(f"⚠️ Reemplazar {alcance} existente?") if existe else True
                
                if st.button("💾 GUARDAR EN HISTÓRICO"):
                    if confirmar:
                        # Filtrar para eliminar el registro idéntico previo
                        df_hist = df_hist[~((df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Alcance'] == alcance))]
                        nueva_fila = pd.DataFrame([{
                            "Mes": mes_sel, "Año": ano_sel, "Tipo": "Técnica", "Alcance": alcance,
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Datos_JSON": df_v.to_json(orient='split')
                        }])
                        df_hist_final = pd.concat([df_hist, nueva_fila], ignore_index=True)
                        if guardar_excel_en_github(df_hist_final, "historico_mallas.xlsx"):
                            st.success(f"✅ {alcance} de {mes_sel} guardado exitosamente."); st.balloons()
                    else: st.error("Debe marcar la confirmación de reemplazo.")

        with tab2:
            st.subheader("Configuración Auxiliares")
            with st.expander("📅 Equipos Auxiliares", expanded=True):
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
                    st.dataframe(piv_ax[sorted(piv_ax.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_ax), use_container_width=True)

        with tab3:
            st.subheader("Consultar Histórico")
            df_h_view = leer_excel_de_github("historico_mallas.xlsx")
            if df_h_view is not None and not df_h_view.empty:
                df_h_view = df_h_view.sort_values(by="Fecha", ascending=False)
                opciones = range(len(df_h_view))
                
                def fmt_safe(x): 
                    row = df_h_view.iloc[x]
                    alc = row.get('Alcance', 'Mes Completo')
                    return f"{row.get('Tipo','Técnica')} | {alc} | {row.get('Mes','N/A')} {row.get('Año','')} ({row.get('Fecha','S/F')})"
                
                sel = st.selectbox("Versiones disponibles", opciones, format_func=fmt_safe)
                
                if st.button("🔍 CARGAR VERSIÓN"):
                    m_rec = reconstruir_malla_desde_json(df_h_view.iloc[sel]['Datos_JSON'])
                    if m_rec is not None:
                        st.session_state['malla_viz'] = m_rec
                        st.session_state['info_viz'] = fmt_safe(sel)
                    else: st.error("No se pudo cargar este registro.")

                if 'malla_viz' in st.session_state:
                    st.divider()
                    st.success(f"Visualizando: {st.session_state['info_viz']}")
                    df_v = st.session_state['malla_viz']
                    try:
                        if 'Grupo' in df_v.columns:
                            piv_v = df_v.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                            st.dataframe(piv_v[sorted(piv_v.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_malla), use_container_width=True)
                        else:
                            piv_v = df_v.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                            st.dataframe(piv_v[sorted(piv_v.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_ax), use_container_width=True)
                    except Exception as e:
                        st.error(f"Error al organizar los datos: {e}")
                    
                    if st.button("Cerrar Vista"):
                        del st.session_state['malla_viz']; st.rerun()
            else: st.info("No hay historial.")

    # --- OTROS MÓDULOS ---
    elif menu == "🏠 Inicio":
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
                <h1>Bienvenido Richard</h1>
                <p>Sistema de Programación Green Móvil | Período: {mes_sel} {ano_sel}</p>
            </div>
        """, unsafe_allow_html=True)

    elif menu == "👥 Base de Datos":
        st.header("Base de Datos Maestra")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_raw.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="base_datos_movilgo.xlsx")

    elif menu == "⚙️ Usuarios":
        if st.session_state['rol'] != "Admin":
            st.error("Acceso restringido."); return
        st.header("Gestión de Usuarios")
        t1, t2 = st.tabs(["Nuevo Usuario", "Lista"])
        with t1:
            with st.form("new_user"):
                n = st.text_input("Nombre"); c = st.text_input("Correo"); r = st.selectbox("Rol", ["Admin", "Planificador", "Visualizador"]); p = st.text_input("Password", type="password")
                if st.form_submit_button("REGISTRAR"):
                    if n and c and p:
                        df_u_new = pd.concat([df_users, pd.DataFrame([[n,c,r,p]], columns=df_users.columns)], ignore_index=True)
                        if guardar_excel_en_github(df_u_new, "usuarios.xlsx"):
                            st.success("Usuario sincronizado."); st.rerun()
        with t2:
            st.table(df_users[["Nombre", "Correo", "Rol"]])

if __name__ == "__main__":
    run_app()
