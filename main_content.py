import streamlit as st
import pandas as pd
import io
import os
import json
from datetime import datetime

# Importación de módulos personalizados
from github_utils import guardar_excel_en_github, leer_excel_de_github
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool
from styles import estilo_malla, estilo_ax

def run_app():
    # --- CONFIGURACIÓN Y CONSTANTES ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'rol' not in st.session_state:
        st.session_state['rol'] = None

    # 1. Cargar Usuarios desde GitHub para validación de Login
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
            st.markdown('<div class="brand-subtitle">Gestión de Operaciones Green Móvil</div>', unsafe_allow_html=True)
            
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
                        st.error("Credenciales incorrectas")
            st.markdown('</div>', unsafe_allow_html=True)
        return

    # --- PANEL PRINCIPAL ---
    df_raw = load_base()
    
    with st.sidebar:
        if os.path.exists(LOGO_PATH): 
            st.image(LOGO_PATH, use_container_width=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        menu_options = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        if st.session_state['rol'] == "Admin":
            menu_options.append("⚙️ Usuarios")
            
        menu = st.radio("Menú", menu_options, label_visibility="collapsed")
        
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        
        if st.button("Cerrar Sesión"):
            st.session_state['auth'] = False
            st.rerun()

    # --- MÓDULOS DE NAVEGACIÓN ---

    if menu == "🏠 Inicio":
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
                <h1>Bienvenido Richard Guevara</h1>
                <p>Rol: {st.session_state['rol']} | Período: {mes_sel} {ano_sel}</p>
            </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Sistema", "Sincronizado", "GitHub")
        col2.metric("Base Operativa", f"{len(df_raw) if df_raw is not None else 0} Empleados")
        col3.metric("Acceso", st.session_state['rol'])

    elif menu == "📊 Gestión de Mallas":
        # Cargamos el histórico desde GitHub para validaciones
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        tab_tec, tab_aux, tab_hist = st.tabs(["Malla Técnica", "Malla Auxiliares", "📜 Histórico Guardado"])

        with tab_tec:
            st.subheader("Configuración de Planta")
            c_cfg = st.columns(3)
            m_req = c_cfg[0].number_input("Masters", 1, 5, 2)
            ta_req = c_cfg[1].number_input("Tec A", 1, 15, 7)
            tb_req = c_cfg[2].number_input("Tec B", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cg = st.columns(4)
                for i in range(4):
                    with cg[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"tec_n_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"tec_d_{i}")
                        es_disp = st.checkbox("Disp.", value=(i==3), key=f"tec_t_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                df_res = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num)
                st.session_state['malla_tec_temp'] = df_res
                st.success("Malla generada. Puede guardarla en el histórico.")

            if 'malla_tec_temp' in st.session_state:
                df_viz = st.session_state['malla_tec_temp']
                piv = df_viz.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.dataframe(piv[sorted(piv.columns, key=lambda x: int(x.split('-')[0]))].style.map(estilo_malla), use_container_width=True)

                # LÓGICA DE GUARDADO E HISTÓRICO
                st.divider()
                st.subheader("💾 Guardar en GitHub")
                
                existe = not df_hist[(df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Tipo'] == "Técnica")].empty
                
                if existe:
                    st.warning(f"⚠️ Ya existe una malla para {mes_sel} {ano_sel}.")
                    confirmar = st.checkbox("¿Está seguro de reemplazar la versión existente?")
                else:
                    confirmar = True

                if st.button("CONFIRMAR GUARDADO DEFINITIVO"):
                    if confirmar:
                        df_hist = df_hist[~((df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Tipo'] == "Técnica"))]
                        nueva_data = pd.DataFrame([{
                            "Mes": mes_sel, "Año": ano_sel, "Tipo": "Técnica",
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Datos_JSON": st.session_state['malla_tec_temp'].to_json()
                        }])
                        df_hist = pd.concat([df_hist, nueva_data], ignore_index=True)
                        if guardar_excel_en_github(df_hist, "historico_mallas.xlsx"):
                            st.success("✅ Guardado exitoso.")
                            st.balloons()
                    else:
                        st.error("Debe confirmar el reemplazo.")

        with tab_hist:
            st.subheader("Consulta de Historial")
            if not df_hist.empty:
                sel = st.selectbox("Seleccione Versión", range(len(df_hist)), 
                                  format_func=lambda x: f"{df_hist.iloc[x]['Tipo']} - {df_hist.iloc[x]['Mes']} {df_hist.iloc[x]['Año']}")
                if st.button("Recuperar y Visualizar"):
                    m_rec = pd.read_json(io.StringIO(df_hist.iloc[sel]['Datos_JSON']))
                    st.write(f"### Mostrando: {df_hist.iloc[sel]['Mes']} {df_hist.iloc[sel]['Año']}")
                    st.dataframe(m_rec, use_container_width=True)
            else:
                st.info("No hay registros en el histórico.")

    elif menu == "⚙️ Usuarios":
        if st.session_state['rol'] != "Admin":
            st.error("Acceso restringido.")
            return

        st.header("Gestión de Usuarios")
        with st.form("form_usuarios_sync"):
            n = st.text_input("Nombre"); c = st.text_input("Correo"); r = st.selectbox("Rol", ["Admin", "Planificador", "Visualizador"]); p = st.text_input("Password", type="password")
            if st.form_submit_button("REGISTRAR Y SINCRONIZAR"):
                if n and c and p:
                    nuevo_u = pd.DataFrame([[n, c, r, p]], columns=["Nombre", "Correo", "Rol", "Password"])
                    df_users = pd.concat([df_users, nuevo_u], ignore_index=True)
                    if guardar_excel_en_github(df_users, "usuarios.xlsx"):
                        st.success(f"Usuario {n} sincronizado.")
                        st.rerun()
                else: st.warning("Complete todos los campos.")

    elif menu == "👥 Base de Datos":
        st.header("Base de Datos Maestra")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_raw.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="base_empleados.xlsx")
