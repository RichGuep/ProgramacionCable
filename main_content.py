import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime, timedelta

# Importes de tus módulos locales
from database import read_db, save_db
from logic import load_base, generar_malla_tecnica_pulp
from styles import estilo_malla, get_login_styles

def run_app():
    # --- CONFIGURACIÓN DE INTERFAZ ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # --- CARGA DE DATOS ---
    df_users = read_db("usuarios")
    df_raw = read_db("empleados")
    if df_raw is None:
        df_raw = load_base()

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        st.markdown(get_login_styles(), unsafe_allow_html=True)
        _, col_login, _ = st.columns([1, 2, 1])
        with col_login:
            if os.path.exists(LOGO_PATH): st.image(LOGO_PATH)
            st.markdown('### 🔐 MovilGo Admin')
            with st.form("Login"):
                u = st.text_input("Usuario")
                p = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR", use_container_width=True):
                    # Validación contra DB (por defecto Richard / Admin2026 si la DB está vacía)
                    if (u == "richard.guevara@greenmovil.com.co" and p == "Admin2026") or \
                       (not df_users.empty and u in df_users['Correo'].values):
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Acceso denegado")
        return

    # --- NAVEGACIÓN ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú", opciones, index=opciones.index(st.session_state['menu_actual']))
        st.divider()
        if st.button("🚪 Salir"):
            st.session_state['auth'] = False
            st.rerun()

    # --- MODULO: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación de Operaciones")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros y Turnos", "⚡ Vista Previa y Resumen", "📜 Histórico"])

        with tab1:
            # 1. Rango de Fechas y Cupos
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                st.subheader("📅 Período de Trabajo")
                rango = st.date_input("Inicio y Fin", value=(datetime(2026, 4, 1), datetime(2026, 4, 30)))
            
            with c_cupos:
                st.subheader("👥 Cupos y 🕒 Horarios")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                t1_h = c1.text_input("Horario T1", "06:00-14:00")
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                t2_h = c2.text_input("Horario T2", "14:00-22:00")
                b_cupo = c3.number_input("Tec B", 1, 20, 3)
                t3_h = c3.text_input("Horario T3", "22:00-06:00")

            st.divider()
            
            # 2. Configuración de Grupos
            st.subheader("🛠️ Grupos de Trabajo")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nom = st.text_input(f"Nombre", f"GRUPO {i+1}", key=f"gn_{i}")
                    des = st.selectbox(f"Descanso", DIAS_SEMANA, index=i if i<3 else 6, key=f"gd_{i}")
                    tip = st.radio(f"Tipo", ["ROTA", "DISP"], index=0 if i<3 else 1, key=f"gt_{i}")
                    n_map[f"G{i+1}"], d_map[nom], t_map[nom] = nom, des, tip

            if st.button("🚀 GENERAR PROGRAMACIÓN", use_container_width=True):
                if len(rango) == 2:
                    st.session_state['horarios'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}
                    f_i, f_f = rango
                    malla = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_cupo, a_cupo, b_cupo, f_i.year, f_i.month, {"inicio": f_i, "fin": f_f})
                    st.session_state['temp_malla'] = malla
                    st.session_state['rango_ref'] = rango
                    st.success("Malla generada. Revise la siguiente pestaña.")
                else:
                    st.error("Seleccione un rango válido.")

        with tab2:
            if 'temp_malla' in st.session_state:
                f_i, f_f = st.session_state['rango_ref']
                h = st.session_state.get('horarios', {})
                st.subheader(f"📋 Malla: {f_i.strftime('%d/%m')} al {f_f.strftime('%d/%m')}")
                st.caption(f"Horarios Aplicados: T1({h.get('T1')}) | T2({h.get('T2')}) | T3({h.get('T3')})")
                
                # Visualización
                st.dataframe(st.session_state['temp_malla'].style.map(estilo_malla), use_container_width=True)
                
                # --- RESUMEN GENERAL ---
                st.divider()
                st.subheader("📊 Resumen Ejecutivo (Conteo Diario)")
                m_t = st.session_state['temp_malla'].T
                resumen = []
                for fecha in m_t.index:
                    counts = m_t[fecha].value_counts()
                    resumen.append({
                        "Fecha": fecha,
                        "En Turno": counts.get("T1", 0) + counts.get("T2", 0) + counts.get("T3", 0),
                        "Descanso (D)": counts.get("D", 0),
                        "Disponible (X)": counts.get("X", 0)
                    })
                df_res = pd.DataFrame(resumen).set_index("Fecha")
                st.table(df_res.T) # Detalle rápido horizontal
                
                if st.button("💾 GUARDAR DEFINITIVAMENTE EN GITHUB", use_container_width=True):
                    malla_json = st.session_state['temp_malla'].to_json(orient='split')
                    nueva = pd.DataFrame([{
                        "Mes": f_i.strftime("%B"), "Año": f_i.year,
                        "Rango": f"{f_i} a {f_f}", "Fecha_Crea": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json, "Horarios": str(h)
                    }])
                    df_h = read_db("historico_mallas")
                    if df_h is None: df_h = pd.DataFrame(columns=["Mes", "Año", "Rango", "Fecha_Crea", "Datos_JSON", "Horarios"])
                    if save_db(pd.concat([df_h, nueva], ignore_index=True), "historico_mallas"):
                        st.success("✅ Malla sincronizada en GitHub.")
            else:
                st.warning("No hay datos generados.")

        with tab3:
            st.subheader("📜 Mallas Guardadas")
            df_hist = read_db("historico_mallas")
            if df_hist is not None and not df_hist.empty:
                for i, row in df_hist.iterrows():
                    with st.expander(f"Malla {row['Mes']} {row['Año']} - ({row['Rango']})"):
                        st.write(f"Creada el: {row['Fecha_Crea']}")
                        if st.button("Recuperar esta versión", key=f"rec_{i}"):
                            st.session_state['temp_malla'] = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.rerun()
            else:
                st.info("Historial vacío.")

    # --- MODULO: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)
        with st.form("new_tec"):
            st.subheader("Añadir Personal")
            n = st.text_input("Nombre")
            c = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar Técnico"):
                if n:
                    nuevo = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    if save_db(nuevo, "empleados"):
                        st.success("Guardado"); st.rerun()

    # --- MODULO: INICIO ---
    else:
        st.title("🚀 Panel de Control MovilGo")
        st.write(f"Técnicos activos: {len(df_raw)}")
        st.info("Seleccione una opción en el menú lateral para operar.")

if __name__ == "__main__":
    run_app()
