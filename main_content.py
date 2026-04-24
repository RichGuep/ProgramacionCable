import streamlit as st
import pandas as pd
import io
import os
import calendar
from datetime import datetime

# Importamos las funciones de nuestros otros archivos
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool
from styles import estilo_malla, estilo_ax
from github_utils import guardar_excel_en_github

def run_app():
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    # 1. Inicializar estados de sesión
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'rol' not in st.session_state:
        st.session_state['rol'] = None

    # 2. Cargar Base de Usuarios desde Excel (Sincronizada con GitHub)
    if os.path.exists("usuarios.xlsx"):
        df_users = pd.read_excel("usuarios.xlsx")
    else:
        # Base inicial por si el archivo no existe en el primer despliegue
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
                    # Verificación contra Excel de GitHub
                    user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                    
                    # Acceso Maestro (Richard siempre entra)
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'] = True
                        st.session_state['rol'] = "Admin"
                        st.rerun()
                    elif not user_match.empty:
                        st.session_state['auth'] = True
                        st.session_state['rol'] = user_match.iloc[0]['Rol']
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
        # Restricción de rol Visualizador
        if st.session_state['rol'] == "Visualizador":
            st.warning("⚠️ Su cuenta tiene rol de 'Visualizador'. No tiene permisos para modificar parámetros o generar nuevas mallas.")
        
        tab1, tab2 = st.tabs(["Planta Técnica", "Auxiliares"])

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
                if st.session_state['rol'] == "Visualizador":
                    st.error("Acción no permitida.")
                elif df_raw is not None:
                    df_f = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num)
                    piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                    cols_ord = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
                    st.dataframe(piv[cols_ord].style.map(estilo_malla), use_container_width=True)

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
                if st.session_state['rol'] == "Visualizador":
                    st.error("Acción no permitida.")
                else:
                    df_res_ax = generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num)
                    if df_res_ax is not None:
                        piv_ax = df_res_ax.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                        cols_ax_ord = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))
                        st.dataframe(piv_ax[cols_ax_ord].style.map(estilo_ax), use_container_width=True)

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
                
                # BOTÓN DENTRO DEL FORMULARIO
                btn_reg = st.form_submit_button("REGISTRAR Y SINCRONIZAR CON GITHUB")
                
                if btn_reg:
                    if new_nom and new_cor and new_pwd:
                        # Crear el nuevo registro
                        nuevo_u = pd.DataFrame([[new_nom, new_cor, new_rol, new_pwd]], 
                                                columns=["Nombre", "Correo", "Rol", "Password"])
                        # Unir con la lista cargada al inicio
                        df_users_final = pd.concat([df_users, nuevo_u], ignore_index=True)
                        
                        # Guardar localmente
                        df_users_final.to_excel("usuarios.xlsx", index=False)
                        
                        # Subir a GitHub y mostrar éxito
                        if guardar_excel_en_github(df_users_final, "usuarios.xlsx"):
                            st.success(f"✅ ¡Usuario '{new_nom}' creado y sincronizado con GitHub exitosamente!")
                            st.balloons() # Toque visual de éxito
                            st.rerun()
                    else:
                        st.warning("⚠️ Todos los campos son obligatorios.")

        with t_lista:
            st.subheader("Usuarios Registrados")
            st.table(df_users[["Nombre", "Correo", "Rol"]])
