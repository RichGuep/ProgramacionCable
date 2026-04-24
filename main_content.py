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
                        # 1. Eliminar anterior para evitar duplicados en el mismo archivo
                        df_hist = df_hist[~((df_hist['Mes'] == mes_sel) & 
                                           (df_hist['Año'] == ano_sel) & 
                                           (df_hist['Tipo'] == "Técnica"))]
                        
                        # 2. Convertir DataFrame a JSON string (formato compacto)
                        malla_json = res.to_json(orient='records') # 'records' es más estable
                        
                        nueva_fila = pd.DataFrame([{
                            "Mes": mes_sel, 
                            "Año": ano_sel, 
                            "Tipo": "Técnica",
                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "Datos_JSON": malla_json
                        }])
                        
                        # 3. Consolidar y subir
                        df_hist_final = pd.concat([df_hist, nueva_fila], ignore_index=True)
                        
                        if guardar_excel_en_github(df_hist_final, "historico_mallas.xlsx"):
                            st.success("✅ ¡Malla sincronizada con GitHub!")
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
            st.subheader("Historial de Programaciones Guardadas")
            
            # 1. Intentar leer el histórico
            df_hist_view = leer_excel_de_github("historico_mallas.xlsx")
            
            if df_hist_view is not None and not df_hist_view.empty:
                # Ordenar por lo más reciente
                df_hist_view = df_hist_view.sort_values(by="Fecha", ascending=False)
                
                # Selector de versiones
                opciones = range(len(df_hist_view))
                def formato(x):
                    row = df_hist_view.iloc[x]
                    return f"{row['Tipo']} - {row['Mes']} {row['Año']} (Creado: {row['Fecha']})"
                
                seleccion = st.selectbox("Seleccione una malla para visualizar", opciones, format_func=formato)
                
               if st.button("🔍 CARGAR VERSIÓN SELECCIONADA"):
                    json_str = df_hist_view.iloc[seleccion]['Datos_JSON']
                    
                    try:
                        # Intentar leer con el nuevo formato 'records'
                        m_rec = pd.read_json(io.StringIO(json_str), orient='records')
                        
                        if m_rec is not None and not m_rec.empty:
                            st.session_state['malla_recuperada_viz'] = m_rec
                            st.session_state['info_malla_viz'] = f"{df_hist_view.iloc[seleccion]['Mes']} {df_hist_view.iloc[seleccion]['Año']}"
                        else:
                            st.error("La malla recuperada parece estar vacía.")
                    except:
                        # Si falla, intentar lectura estándar (para mallas viejas)
                        try:
                            m_rec = pd.read_json(io.StringIO(json_str))
                            st.session_state['malla_recuperada_viz'] = m_rec
                        except:
                            st.error("No se pudo reconstruir esta malla. Formato incompatible.")

                # 2. MOSTRAR LA MALLA (Si existe en el estado de sesión)
                if 'malla_recuperada_viz' in st.session_state:
                    st.divider()
                    st.success(f"📅 Visualizando Histórico: {st.session_state['info_malla_viz']}")
                    
                    df_viz = st.session_state['malla_recuperada_viz']
                    
                    # Identificamos si es Técnica o Auxiliar por las columnas
                    if 'Grupo' in df_viz.columns:
                        piv_rec = df_viz.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                        # Ordenar columnas por número de día
                        cols_ord = sorted(piv_rec.columns, key=lambda x: int(str(x).split('-')[0]))
                        st.dataframe(piv_rec[cols_ord].style.map(estilo_malla), use_container_width=True)
                    else:
                        # Si es de auxiliares
                        piv_rec = df_viz.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                        cols_ord = sorted(piv_rec.columns, key=lambda x: int(str(x).split('-')[0]))
                        st.dataframe(piv_rec[cols_ord].style.map(estilo_ax), use_container_width=True)
                    
                    # Botón para limpiar la vista
                    if st.button("Cerrar Visualización"):
                        del st.session_state['malla_recuperada_viz']
                        st.rerun()
            else:
                st.info("No se encontraron mallas guardadas en GitHub.")
