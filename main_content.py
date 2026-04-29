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
                    n_map[i+1] = nom
                    d_map[nom] = des
                    t_map[nom] = tip

            if st.button("🚀 GENERAR MALLA ÓPTIMA", use_container_width=True):
                if isinstance(rango, tuple) and len(rango) == 2:
                    f_i, f_f = rango
                    
                    def parse_h(h_str):
                        p = h_str.split("-")
                        return {"inicio": p[0].strip(), "fin": p[1].strip()} if "-" in h_str else {"inicio": h_str, "fin": ""}

                    dict_horarios = {"T1": parse_h(t1_h), "T2": parse_h(t2_h), "T3": parse_h(t3_h)}
                    st.session_state['horarios_labels'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}

                    with st.spinner("Optimizando cobertura y balanceando descansos..."):
                        malla_long = generar_malla_tecnica_pulp(
                            df_raw, n_map, d_map, t_map, m_cupo, a_cupo, b_cupo, 
                            f_i.year, f_i.month, dict_horarios
                        )
                    
                    if not malla_long.empty:
                        st.session_state['temp_malla'] = malla_long
                        st.session_state['rango_ref'] = rango
                        st.success("Malla generada con éxito.")
                    else:
                        st.error("No se pudo generar la malla.")

        with tab2:
            if 'temp_malla' in st.session_state:
                df_long = st.session_state['temp_malla']
                f_i, f_f = st.session_state['rango_ref']
                h_lab = st.session_state.get('horarios_labels', {})

                # --- VISTA HORIZONTAL ---
                df_horiz = df_long.pivot_table(
                    index=['Grupo', 'Empleado', 'Cargo'], 
                    columns='Dia', 
                    values='Turno', 
                    aggfunc='first'
                ).reset_index()

                st.subheader("🔍 Filtros de Visualización")
                f1, f2, f3 = st.columns(3)
                with f1: g_sel = st.multiselect("Grupo", df_horiz['Grupo'].unique())
                with f2: r_sel = st.multiselect("Cargo", df_horiz['Cargo'].unique())
                with f3: p_sel = st.multiselect("Persona", df_horiz['Empleado'].unique())

                df_f = df_horiz.copy()
                if g_sel: df_f = df_f[df_f['Grupo'].isin(g_sel)]
                if r_sel: df_f = df_f[df_f['Cargo'].isin(r_sel)]
                if p_sel: df_f = df_f[df_f['Empleado'].isin(p_sel)]

                st.subheader(f"📅 Cronograma de Turnos ({f_i.strftime('%d/%m')} - {f_f.strftime('%d/%m')})")
                st.dataframe(df_f.style.map(estilo_malla), use_container_width=True)

                # --- RESUMEN Y AUDITORÍA DE COBERTURA ---
                st.divider()
                st.header("📊 Resumen y Auditoría de Cobertura")

                # 1. RESUMEN CONSOLIDADO (TODO EL MES)
                st.subheader("📈 Totales Consolidados del Periodo")
                st.write("Conteo total de turnos y descansos asignados a cada cargo en todo el mes:")
                resumen_mensual = pd.crosstab(
                    index=df_long['Cargo'],
                    columns=df_long['Turno'],
                    margins=True,
                    margins_name="TOTAL ACUMULADO"
                )
                st.dataframe(resumen_mensual, use_container_width=True)

                # 2. ANÁLISIS DETALLADO POR DÍA
                st.divider()
                st.subheader("📅 Detalle Específico por Día")
                lista_dias = df_long['Dia'].unique()
                dia_analisis = st.selectbox("Seleccione un día para auditar asistencia:", lista_dias)
                df_dia = df_long[df_long['Dia'] == dia_analisis]

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("👷 Trabajando", df_dia[df_dia['Turno'].isin(['T1', 'T2', 'T3', 'T1 (Apoyo)'])].shape[0])
                m2.metric("🏖️ Descanso Ley", df_dia[df_dia['Turno'] == 'DESC. LEY'].shape[0])
                m3.metric("🔄 Compensatorios", df_dia[df_dia['Turno'] == 'DESC. COMPENSATORIO'].shape[0])
                m4.metric("👥 Total Personal", df_dia.shape[0])

                st.write(f"**Distribución de Cargos el día {dia_analisis}:**")
                resumen_dia = pd.crosstab(index=df_dia['Cargo'], columns=df_dia['Turno'])
                st.table(resumen_dia)

                # 3. CONTROL DE EQUIDAD (BALANCE 2+2)
                st.divider()
                st.subheader("⚖️ Control de Equidad (Balance de Descansos)")
                df_balance = df_long[df_long['Turno'].str.contains('DESC')].copy()
                if not df_balance.empty:
                    df_balance_count = df_balance.groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
                    st.bar_chart(df_balance_count)
                    st.caption("Verifique que los grupos tengan un balance cercano (Ej: 2 Ley y 2 Compensatorios).")

                if st.button("💾 GUARDAR DEFINITIVAMENTE", use_container_width=True):
                    malla_json = df_long.to_json(orient='split')
                    nueva = pd.DataFrame([{
                        "Mes": f_i.strftime("%B %Y"), "Rango": f"{f_i} a {f_f}",
                        "Fecha_Crea": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json, "Horarios": str(h_lab)
                    }])
                    df_h = read_db("historico_mallas")
                    if df_h is None: df_h = pd.DataFrame(columns=["Mes", "Rango", "Fecha_Crea", "Datos_JSON", "Horarios"])
                    if save_db(pd.concat([df_h, nueva], ignore_index=True), "historico_mallas"):
                        st.success("✅ Guardado en el historial.")
            else:
                st.info("👋 Genere la malla en la pestaña anterior para ver el resumen.")

        with tab3:
            st.subheader("📜 Histórico de Versiones")
            df_hist = read_db("historico_mallas")
            if df_hist is not None and not df_hist.empty:
                for i, row in df_hist.iloc[::-1].iterrows():
                    with st.expander(f"📅 {row['Mes']} - Creada: {row['Fecha_Crea']}"):
                        if st.button("Cargar esta versión", key=f"h_{i}"):
                            st.session_state['temp_malla'] = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.rerun()

    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)

    else:
        st.title("🚀 MovilGo Admin")
        st.write(f"Técnicos activos en base: {len(df_raw)}")

if __name__ == "__main__":
    run_app()
