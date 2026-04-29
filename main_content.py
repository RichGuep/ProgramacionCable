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
                    if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
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
        st.header("📊 Programación Operativa de Turnos")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros y Turnos", "⚡ Vista Horizontal y Resumen", "📜 Histórico"])

        with tab1:
            # 1. Rango de Fechas y Cupos
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                st.subheader("📅 Período")
                rango = st.date_input("Inicio y Fin", value=(datetime(2026, 4, 1), datetime(2026, 4, 30)))
            
            with c_cupos:
                st.subheader("👥 Cupos y 🕒 Horarios")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                t1_h = c1.text_input("T1 (Mañana)", "06:00-14:00")
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                t2_h = c2.text_input("T2 (Tarde)", "14:00-22:00")
                b_cupo = c3.number_input("Tec B", 1, 20, 3)
                t3_h = c3.text_input("T3 (Noche)", "22:00-06:00")

            st.divider()
            st.subheader("🛠️ Configuración de Grupos")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nom = st.text_input(f"Nombre", f"GRUPO {i+1}", key=f"gn_{i}")
                    des = st.selectbox(f"Descanso", DIAS_SEMANA, index=i if i<3 else 6, key=f"gd_{i}")
                    tip = st.radio(f"Tipo", ["ROTA", "DISP"], index=0 if i<3 else 1, key=f"gt_{i}")
                    n_map[f"G{i+1}"], d_map[nom], t_map[nom] = nom, des, tip

            if st.button("🚀 GENERAR MALLA ÓPTIMA", use_container_width=True):
                if len(rango) == 2:
                    st.session_state['horarios'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}
                    f_i, f_f = rango
                    malla_long = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_cupo, a_cupo, b_cupo, f_i.year, f_i.month, {"inicio": f_i, "fin": f_f})
                    st.session_state['temp_malla'] = malla_long
                    st.session_state['rango_ref'] = rango
                    st.success("Malla generada con éxito.")
                else:
                    st.error("Seleccione un rango válido.")

        with tab2:
            if 'temp_malla' in st.session_state:
                df_long = st.session_state['temp_malla']
                f_i, f_f = st.session_state['rango_ref']
                h = st.session_state.get('horarios', {})

                # --- TRANSFORMACIÓN A VISTA HORIZONTAL ---
                # Pivotamos la tabla: Empleados en filas, Días en columnas
                df_horiz = df_long.pivot_table(
                    index=['Grupo', 'Empleado', 'Cargo'], 
                    columns='Label', 
                    values='Final', 
                    aggfunc='first'
                ).reset_index()

                st.subheader("🔍 Filtros de Visualización")
                f1, f2, f3 = st.columns(3)
                with f1: g_sel = st.multiselect("Filtrar por Grupo", df_horiz['Grupo'].unique())
                with f2: r_sel = st.multiselect("Filtrar por Rol (Cargo)", df_horiz['Cargo'].unique())
                with f3: p_sel = st.multiselect("Filtrar por Persona", df_horiz['Empleado'].unique())

                df_f = df_horiz.copy()
                if g_sel: df_f = df_f[df_f['Grupo'].isin(g_sel)]
                if r_sel: df_f = df_f[df_f['Cargo'].isin(r_sel)]
                if p_sel: df_f = df_f[df_f['Empleado'].isin(p_sel)]

                st.subheader(f"📅 Cronograma de Turnos ({f_i.strftime('%d/%m')} - {f_f.strftime('%d/%m')})")
                st.caption(f"Horarios: T1: {h.get('T1')} | T2: {h.get('T2')} | T3: {h.get('T3')}")
                st.dataframe(df_f.style.map(estilo_malla), use_container_width=True)

                # --- RESUMEN EJECUTIVO DETALLADO ---
                st.divider()
                st.subheader("📊 Resumen Ejecutivo: Cobertura Diaria")
                
                dias_cols = [c for c in df_f.columns if c not in ['Grupo', 'Empleado', 'Cargo']]
                dia_sel = st.selectbox("Seleccione día para análisis de roles y turnos:", dias_cols)

                # Tabla cruzada: Cargo vs Turno (Muestra cuántos Masters/Tec en T1, T2, etc)
                df_res_dia = df_f.groupby(['Cargo', dia_sel]).size().unstack(fill_value=0)
                
                col_r1, col_r2 = st.columns([2, 1])
                with col_r1:
                    st.markdown(f"**Distribución de Personal el día {dia_sel}**")
                    st.table(df_res_dia)
                
                with col_r2:
                    st.markdown("**Totales Operativos**")
                    conteo = df_f[dia_sel].value_counts()
                    st.metric("Personal en Turno", conteo.get('T1',0)+conteo.get('T2',0)+conteo.get('T3',0))
                    st.metric("En Descanso (D)", conteo.get('D', 0))
                    st.metric("Disponibles (X)", conteo.get('X', 0))

                # --- DESCANSOS POR GRUPO ---
                st.subheader("🏖️ Total Descansos por Grupo (En el período)")
                df_desc = df_f.set_index('Grupo')[dias_cols]
                total_d = (df_desc == 'D').sum(axis=1).groupby(level=0).sum()
                st.bar_chart(total_d)

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
                        st.success("✅ Sincronizado en GitHub.")
            else:
                st.warning("⚠️ Genere la malla en la pestaña de parámetros.")

        with tab3:
            st.subheader("📜 Histórico de Versiones")
            df_hist = read_db("historico_mallas")
            if df_hist is not None and not df_hist.empty:
                for i, row in df_hist.iterrows():
                    m_label = row.get('Mes', 'N/A')
                    r_label = row.get('Rango', 'Sin Rango')
                    with st.expander(f"📅 Malla {m_label} - ({r_label})"):
                        if st.button("Cargar esta versión", key=f"rec_{i}"):
                            st.session_state['temp_malla'] = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.rerun()
            else:
                st.info("No hay mallas guardadas.")

    # --- MODULO: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)
        with st.form("new_tec"):
            st.subheader("Añadir Técnico")
            n = st.text_input("Nombre")
            c = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar"):
                if n:
                    nuevo = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    save_db(nuevo, "empleados")
                    st.rerun()
    else:
        st.title("🚀 MovilGo Admin")
        st.write(f"Técnicos activos: {len(df_raw)}")

if __name__ == "__main__":
    run_app()
