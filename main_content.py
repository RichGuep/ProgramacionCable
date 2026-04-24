import streamlit as st
import pandas as pd
import io
import os
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
        if os.path.exists("usuarios.xlsx"):
            df_users = pd.read_excel("usuarios.xlsx")
        else:
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
                        st.session_state['auth'], st.session_state['rol'] = True, user_match.iloc[0]['Rol']
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas. Verifique su usuario y contraseña.")
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

    # --- NAVEGACIÓN ---
    if menu == "🏠 Inicio":
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
                <h1>Bienvenido al Sistema MovilGo</h1>
                <p>Rol actual: {st.session_state['rol']} | Período: {mes_sel} {ano_sel}</p>
            </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Personal Técnico", "Activo", "Malla PuLP")
        c2.metric("Sincronización", "GitHub", "Conectado")
        c3.metric("Seguridad", st.session_state['rol'], "Nivel Acceso")

    elif menu == "📊 Gestión de Mallas":
        # Cargar histórico para validaciones
        df_hist = leer_excel_de_github("historico_mallas.xlsx")
        if df_hist is None:
            df_hist = pd.DataFrame(columns=["Mes", "Año", "Tipo", "Fecha", "Datos_JSON"])

        if st.session_state['rol'] == "Visualizador":
            st.warning("⚠️ Su cuenta tiene rol de 'Visualizador'. No tiene permisos para modificar parámetros.")
        
        tab1, tab2, tab3 = st.tabs(["⚡ Generador Técnicos", "⚡ Generador Auxiliares", "📜 Histórico"])

        with tab1:
            st.subheader("Configuración Planta Técnica")
            col_cfg = st.columns(3)
            m_req = col_cfg[0].number_input("Masters", 1, 5, 2)
            ta_req = col_cfg[1].number_input("Tec A", 1, 15, 7)
            tb_req = col_cfg[2].number_input("Tec B", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cols = st.columns(4)
                for i in range(4):
                    with cols[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                        d_s = st.selectbox(f"Descanso {g_id}", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                        es_disp = st.checkbox(f"Disponible {g_id}", value=(i==3), key=f"t_b_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                # --- LÓGICA DE EMPALME AUTOMÁTICO ---
                mes_ant_idx = (mes_num - 2) % 12
                mes_ant_nom = meses[mes_ant_idx]
                ano_ant = ano_sel if mes_num > 1 else ano_sel - 1
                
                estado_previo = None
                if not df_hist.empty:
                    ant_data = df_hist[(df_hist['Mes'] == mes_ant_nom) & (df_hist['Año'] == ano_ant) & (df_hist['Tipo'] == "Técnica")]
                    if not ant_data.empty:
                        m_ant = reconstruir_malla_desde_json(ant_data.iloc[0]['Datos_JSON'])
                        if m_ant is not None:
                            cols_dias = [c for c in m_ant.columns if '-' in str(c)]
                            ult_col = sorted(cols_dias, key=lambda x: int(str(x).split('-')[0]))[-1]
                            estado_previo = m_ant.set_index('Grupo')[ult_col].to_dict()
                            st.info(f"🔄 Empalme detectado con {mes_ant_nom}. Continuidad aplicada.")

                if df_raw is not None:
                    st.session_state['temp_malla_tec'] = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, estado_anterior=estado_previo)
                    st.rerun()

            if 'temp_malla_tec' in st.session_state:
                res = st.session_state['temp_malla_tec']
                piv = res.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.dataframe(piv[sorted(piv.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_malla), use_container_width=True)
                
                st.divider()
                # --- ALERTA DE REEMPLAZO ---
                existe = not df_hist[(df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Tipo'] == "Técnica")].empty
                confirmar = True
                if existe:
                    st.warning(f"⚠️ Ya existe una malla guardada para {mes_sel} {ano_sel}.")
                    confirmar = st.checkbox("¿Desea reemplazar el registro existente?")
                
                if st.button("💾 GUARDAR MALLA EN GITHUB"):
                    if confirmar:
                        df_hist = df_hist[~((df_hist['Mes'] == mes_sel) & (df_hist['Año'] == ano_sel) & (df_hist['Tipo'] == "Técnica"))]
                        nueva_fila = pd.DataFrame([{
                            "Mes": mes_sel, "Año": ano_sel, "Tipo": "Técnica",
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Datos_JSON": res.to_json()
                        }])
                        df_hist = pd.concat([df_hist, nueva_fila], ignore_index=True)
                        if guardar_excel_en_github(df_hist, "historico_mallas.xlsx"):
                            st.success("✅ Malla guardada exitosamente.")
                            st.balloons()
                    else:
                        st.error("Debe confirmar para reemplazar.")

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
            st.subheader("Historial de Programaciones")
            if not df_hist.empty:
                df_hist_view = df_hist.sort_values(by="Fecha", ascending=False)
                sel = st.selectbox("Seleccione Versión", range(len(df_hist_view)), 
                                  format_func=lambda x: f"{df_hist_view.iloc[x]['Tipo']} - {df_hist_view.iloc[x]['Mes']} {df_hist_view.iloc[x]['Año']} ({df_hist_view.iloc[x]['Fecha']})")
                
                if st.button("Visualizar Versión Guardada"):
                    try:
                        m_rec = reconstruir_malla_desde_json(df_hist_view.iloc[sel]['Datos_JSON'])
                        if m_rec is not None:
                            st.write(f"### Mostrando: {df_hist_view.iloc[sel]['Mes']} {df_hist_view.iloc[sel]['Año']}")
                            piv_rec = m_rec.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                            st.dataframe(piv_rec[sorted(piv_rec.columns, key=lambda x: int(str(x).split('-')[0]))].style.map(estilo_malla), use_container_width=True)
                    except Exception as e:
                        st.error(f"Error al reconstruir: {e}")
            else:
                st.info("No hay registros guardados.")

    elif menu == "👥 Base de Datos":
        st.header("Base de Datos Maestra")
        if df_raw is not None:
            st.dataframe(df_raw, use_container_width=True)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_raw.to_excel(writer, index=False)
            st.download_button("📥 Descargar Copia Seguridad", data=buffer.getvalue(), file_name="respaldo_datos.xlsx")

    elif menu == "⚙️ Usuarios":
        if st.session_state['rol'] != "Admin":
            st.error("Área restringida solo para administradores.")
            return

        st.header("Gestión de Usuarios y Roles")
        t_crear, t_lista = st.tabs(["Crear Nuevo Usuario", "Lista de Accesos"])

        with t_crear:
            with st.form("form_usuarios_github"):
                st.subheader("Registrar nuevo personal con acceso")
                new_nom = st.text_input("Nombre Completo")
                new_cor = st.text_input("Correo (Usuario de ingreso)")
                new_rol = st.selectbox("Rol en el Sistema", ["Admin", "Planificador", "Visualizador"])
                new_pwd = st.text_input("Contraseña Temporal", type="password")
                btn_reg = st.form_submit_button("REGISTRAR Y SINCRONIZAR CON GITHUB")
                
                if btn_reg:
                    if new_nom and new_cor and new_pwd:
                        nuevo_u = pd.DataFrame([[new_nom, new_cor, new_rol, new_pwd]], columns=["Nombre", "Correo", "Rol", "Password"])
                        df_users_final = pd.concat([df_users, nuevo_u], ignore_index=True)
                        if guardar_excel_en_github(df_users_final, "usuarios.xlsx"):
                            st.success(f"✅ ¡Usuario '{new_nom}' creado con éxito!")
                            st.balloons()
                            st.rerun()
                    else:
                        st.warning("⚠️ Todos los campos son obligatorios.")

        with t_lista:
            st.table(df_users[["Nombre", "Correo", "Rol"]])
