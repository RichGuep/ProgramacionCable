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
        st.header("📊 Programación de Operaciones")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros", "⚡ Vista Previa y Resumen", "📜 Histórico"])

        with tab1:
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                st.subheader("📅 Período")
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
            st.subheader("🛠️ Grupos")
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
                    st.success("Malla generada con éxito.")
                else:
                    st.error("Seleccione un rango válido.")

        with tab2:
            if 'temp_malla' in st.session_state:
                f_i, f_f = st.session_state['rango_ref']
                malla_original = st.session_state['temp_malla']
                
                st.subheader("🔍 Filtros de Visualización")
                col_f1, col_f2, col_f3 = st.columns(3)
                
                with col_f1:
                    filtro_grupo = st.multiselect("Filtrar por Grupo", options=malla_original['Grupo'].unique())
                with col_f2:
                    filtro_persona = st.multiselect("Filtrar por Técnico", options=malla_original['Empleado'].unique())
                with col_f3:
                    # Filtro de sub-rango de fechas dentro de la malla
                    dias_malla = [col for col in malla_original.columns if col not in ['Grupo', 'Empleado', 'Cargo', 'Horario']]
                    rango_v = st.select_slider("Ver días específicos", options=dias_malla, value=(dias_malla[0], dias_malla[-1]))

                # Aplicar Filtros a la data
                df_view = malla_original.copy()
                if filtro_grupo:
                    df_view = df_view[df_view['Grupo'].isin(filtro_grupo)]
                if filtro_persona:
                    df_view = df_view[df_view['Empleado'].isin(filtro_persona)]
                
                # Seleccionar columnas (Info básica + Rango de días filtrado)
                cols_basicas = ['Grupo', 'Empleado', 'Cargo']
                idx_ini = dias_malla.index(rango_v[0])
                idx_fin = dias_malla.index(rango_v[1]) + 1
                cols_dias = dias_malla[idx_ini:idx_fin]
                
                df_view = df_view[cols_basicas + cols_dias]

                st.divider()
                st.subheader(f"📅 Cronograma Horizontal ({rango_v[0]} al {rango_v[1]})")
                st.dataframe(df_view.style.map(estilo_malla), use_container_width=True)

                # --- RESUMEN EJECUTIVO DETALLADO ---
                st.divider()
                st.subheader("📊 Resumen Ejecutivo Detallado")
                
                # Elegir día para ver detalle de turnos y roles
                dia_analisis = st.selectbox("Seleccione día para análisis de cobertura", options=cols_dias)
                
                # Crear matriz de Cobertura: Turno vs Rol
                cobertura = df_view[['Cargo', dia_analisis]].groupby(['Cargo', dia_analisis]).size().unstack(fill_value=0)
                
                col_res1, col_res2 = st.columns([2, 1])
                with col_res1:
                    st.markdown(f"**Distribución de Roles en Turnos ({dia_analisis})**")
                    st.table(cobertura)
                
                with col_res2:
                    st.markdown("**Totales del día**")
                    total_dia = df_view[dia_analisis].value_counts()
                    st.write(f"✅ En Turno: {total_dia.get('T1',0) + total_dia.get('T2',0) + total_dia.get('T3',0)}")
                    st.write(f"🛌 Descansos: {total_dia.get('D', 0)}")
                    st.write(f"📞 Disponibles: {total_dia.get('X', 0)}")

                # --- CONTROL DE DESCANSOS SEMANALES ---
                st.divider()
                st.subheader("🏖️ Control de Descansos por Grupo (Semanal)")
                descansos_grupo = df_view.groupby('Grupo')[cols_dias].apply(lambda x: (x == 'D').sum().sum())
                st.bar_chart(descansos_grupo)
                
                if st.button("💾 GUARDAR DEFINITIVAMENTE EN GITHUB", use_container_width=True):
                    # (Tu lógica de guardado actual...)
                    pass
            else:
                st.warning("⚠️ No hay malla generada para mostrar.")
        with tab3:
            st.subheader("📜 Mallas Guardadas")
            df_hist = read_db("historico_mallas")
            if df_hist is not None and not df_hist.empty:
                for i, row in df_hist.iterrows():
                    # USAMOS .get() PARA EVITAR EL KEYERROR SI LA COLUMNA NO EXISTE
                    mes_label = row.get('Mes', 'N/A')
                    anio_label = row.get('Año', 'N/A')
                    rango_label = row.get('Rango', 'Sin Rango')
                    fecha_label = row.get('Fecha_Crea', row.get('Fecha', 'Fecha Desconocida'))
                    
                    with st.expander(f"📅 {mes_label} {anio_label} - ({rango_label})"):
                        st.write(f"Guardado el: {fecha_label}")
                        if st.button("Recuperar esta versión", key=f"rec_{i}"):
                            st.session_state['temp_malla'] = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.rerun()
            else:
                st.info("Historial vacío.")

    # --- MODULOS RESTANTES (Mantener igual) ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Técnicos")
        st.dataframe(df_raw, use_container_width=True)
        with st.form("new_tec"):
            n = st.text_input("Nombre")
            c = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
            if st.form_submit_button("Guardar"):
                if n:
                    nuevo = pd.concat([df_raw, pd.DataFrame([{"nombre": n.upper(), "cargo": c, "grupo": "SIN GRUPO"}])], ignore_index=True)
                    save_db(nuevo, "empleados")
                    st.rerun()
    else:
        st.title("🚀 MovilGo Admin")
        st.write(f"Técnicos: {len(df_raw)}")

if __name__ == "__main__":
    run_app()
