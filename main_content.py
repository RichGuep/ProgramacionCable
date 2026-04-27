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
    # --- CONFIGURACIÓN Y ESTADOS ---
    LOGO_PATH = "MovilGo.png"
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

    if 'auth' not in st.session_state:
        st.session_state['auth'] = False
    if 'menu_actual' not in st.session_state:
        st.session_state['menu_actual'] = "🏠 Inicio"

    # --- CARGA DE DATOS (SQLite) ---
    df_raw = read_db("empleados")
    if df_raw is None:
        df_raw = load_base()

    # --- LÓGICA DE LOGIN (Se omite por brevedad, mantener la actual) ---
    if not st.session_state['auth']:
        # ... (Tu código de login actual aquí)
        pass

    # --- NAVEGACIÓN LATERAL ---
    with st.sidebar:
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú Principal", opciones, index=opciones.index(st.session_state['menu_actual']))

    # --- MÓDULO 1: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación Técnica")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros", "⚡ Vista Previa", "📜 Histórico"])

        with tab1:
            col_f, col_p = st.columns([1, 2])
            with col_f:
                st.subheader("📅 Período")
                # CAMBIO CLAVE: Selector de rango de fechas
                rango_fechas = st.date_input(
                    "Seleccione Inicio y Fin",
                    value=(datetime(2026, 4, 1), datetime(2026, 4, 30)),
                    key="rango_programacion"
                )
            
            with col_p:
                st.subheader("👥 Cupos Requeridos")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 10, 2)
                a_cupo = c2.number_input("Tec A", 1, 20, 7)
                b_cupo = c3.number_input("Tec B", 1, 20, 3)

            # Validación del rango
            if len(rango_fechas) == 2:
                fecha_inicio, fecha_fin = rango_fechas
                st.caption(f"Días a programar: {(fecha_fin - fecha_inicio).days + 1}")
            else:
                st.warning("Seleccione ambas fechas (Inicio y Fin) en el calendario.")

            st.divider()
            st.subheader("🛠️ Configuración de Grupos y Descansos")
            n_map, d_map, t_map = {}, {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**G{i+1}**")
                    nombre = st.text_input(f"Nombre", f"GRUPO {i+1}", key=f"gn_{i}")
                    descanso = st.selectbox(f"Descanso", DIAS_SEMANA, index=i if i<3 else 6, key=f"gd_{i}")
                    tipo = st.radio(f"Tipo", ["ROTA", "DISP"], index=0 if i<3 else 1, key=f"gt_{i}")
                    n_map[f"G{i+1}"] = nombre; d_map[nombre] = descanso; t_map[nombre] = tipo

            st.divider()
            if st.button("🚀 GENERAR MALLA ÓPTIMA", use_container_width=True):
                if len(rango_fechas) == 2:
                    with st.spinner("Calculando turnos para el rango seleccionado..."):
                        # Se pasan fecha_inicio y fecha_fin a la lógica
                        malla_res = generar_malla_tecnica_pulp(
                            df_raw, n_map, d_map, t_map, 
                            m_cupo, a_cupo, b_cupo, 
                            fecha_inicio.year, fecha_inicio.month, 
                            {"inicio": fecha_inicio, "fin": fecha_fin} # Pasamos el rango como dict
                        )
                        st.session_state['temp_malla'] = malla_res
                        st.session_state['rango_ref'] = rango_fechas
                        st.success("Malla calculada. Revise 'Vista Previa'.")
                else:
                    st.error("Por favor, seleccione un rango válido de fechas.")

        with tab2:
            if 'temp_malla' in st.session_state and 'rango_ref' in st.session_state:
                f_i, f_f = st.session_state['rango_ref']
                st.subheader(f"Malla: {f_i.strftime('%d/%m/%Y')} al {f_f.strftime('%d/%m/%Y')}")
                st.dataframe(st.session_state['temp_malla'].style.map(estilo_malla), use_container_width=True)
                
                if st.button("💾 CONFIRMAR Y GUARDAR EN GITHUB", use_container_width=True):
                    malla_json = st.session_state['temp_malla'].to_json(orient='split')
                    nueva_entrada = pd.DataFrame([{
                        "Mes": f_i.strftime("%B"),
                        "Año": f_i.year,
                        "Rango": f"{f_i} a {f_f}",
                        "Fecha_Crea": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "Datos_JSON": malla_json
                    }])
                    df_h = read_db("historico_mallas")
                    if df_h is None: df_h = pd.DataFrame(columns=["Mes", "Año", "Rango", "Fecha_Crea", "Datos_JSON"])
                    if save_db(pd.concat([df_h, nueva_entrada], ignore_index=True), "historico_mallas"):
                        st.success("✅ Malla guardada en histórico.")
            else:
                st.warning("⚠️ No hay datos generados.")

        with tab3:
            st.subheader("📜 Mallas Anteriores")
            df_hist_full = read_db("historico_mallas")
            if df_hist_full is not None and not df_hist_full.empty:
                for i, row in df_hist_full.iterrows():
                    with st.expander(f"📅 {row['Mes']} {row['Año']} - (Guardado: {row['Fecha']})"):
                        if st.button("Cargar versión", key=f"v_{i}"):
                            df_recup = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.session_state['temp_malla'] = df_recup
                            st.info("Versión cargada. Ver en la pestaña 'Vista Previa'.")
            else:
                st.info("El histórico está vacío.")

    # --- MÓDULO 2: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)
        
        with st.form("new_tech"):
            st.subheader("➕ Registrar Nuevo Personal")
            n = st.text_input("Nombre y Apellidos")
            c = st.selectbox("Categoría", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar en Base de Datos"):
                if n:
                    nuevo_personal = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    if save_db(nuevo_personal, "empleados"):
                        st.success(f"Técnico {n} registrado con éxito."); st.rerun()
                else:
                    st.error("Debe ingresar un nombre válido.")

    # --- MÓDULO 3: INICIO ---
    else:
        st.title("🚀 MovilGo Admin")
        st.markdown(f"### Bienvenida, Richard.")
        st.write(f"Estado de la base de datos: **{len(df_raw)} técnicos activos.**")
        st.info("Seleccione 'Gestión de Mallas' para programar el mes o 'Base de Datos' para editar el personal.")

if __name__ == "__main__":
    run_app()
