import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

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

    # --- NAVEGACIÓN LATERAL ---
    with st.sidebar:
        if os.path.exists(LOGO_PATH): st.image(LOGO_PATH, use_container_width=True)
        st.divider()
        opciones = ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"]
        st.session_state['menu_actual'] = st.radio("Menú", opciones, index=opciones.index(st.session_state['menu_actual']))
        st.divider()
        if st.button("🚪 Salir"):
            st.session_state['auth'] = False
            st.rerun()

    # --- MÓDULO: GESTIÓN DE MALLAS ---
    if st.session_state['menu_actual'] == "📊 Gestión de Mallas":
        st.header("📊 Programación Operativa de Turnos")
        tab1, tab2, tab3 = st.tabs(["⚙️ Parámetros y Grupos", "⚡ Vista Horizontal", "📜 Histórico"])

        with tab1:
            # 1. Configuración de Cupos y Horarios
            c_fechas, c_cupos = st.columns([1.5, 2])
            with c_fechas:
                st.subheader("📅 Período")
                # Valor por defecto abril 2026 según tu contexto
                rango = st.date_input("Rango de Fechas", value=(datetime(2026, 4, 1), datetime(2026, 4, 30)))
            
            with c_cupos:
                st.subheader("👥 Requerimientos por Turno")
                c1, c2, c3 = st.columns(3)
                m_cupo = c1.number_input("Masters", 1, 5, 2)
                t1_h = c1.text_input("Horario T1", "06:00-14:00")
                
                a_cupo = c2.number_input("Téc. A", 1, 15, 7)
                t2_h = c2.text_input("Horario T2", "14:00-22:00")
                
                b_cupo = c3.number_input("Téc. B", 1, 15, 3)
                t3_h = c3.text_input("Horario T3", "22:00-06:00")

            st.divider()
            
            # 2. Configuración de Grupos (Automatizada: Solo nombre y descanso)
            st.subheader("🛠️ Configuración de Grupos y Descansos")
            st.info("El sistema asignará automáticamente la rotación (T1, T2, T3) y el apoyo basándose en la cobertura necesaria.")
            
            n_map, d_map = {}, {}
            cols_g = st.columns(4)
            for i in range(4):
                with cols_g[i]:
                    st.markdown(f"**Célula G{i+1}**")
                    nombre_g = st.text_input(f"Nombre Grupo", f"GRUPO {i+1}", key=f"gn_{i}")
                    descanso_g = st.selectbox(f"Día Descanso", DIAS_SEMANA, index=i if i < 3 else 6, key=f"gd_{i}")
                    
                    n_map[i+1] = nombre_g
                    d_map[nombre_g] = descanso_g

            if st.button("🚀 GENERAR MALLA CON ROTACIÓN AUTOMÁTICA", use_container_width=True):
                if isinstance(rango, tuple) and len(rango) == 2:
                    f_i, f_f = rango
                    
                    # Función para procesar texto de horario a diccionario
                    def parse_h(s):
                        if "-" in s:
                            p = s.split("-")
                            return {"inicio": p[0].strip(), "fin": p[1].strip()}
                        return {"inicio": s, "fin": ""}

                    dict_horarios = {
                        "T1": parse_h(t1_h),
                        "T2": parse_h(t2_h),
                        "T3": parse_h(t3_h),
                        "X": {"inicio": "Apoyo", "fin": "Variable"}
                    }
                    
                    with st.spinner("Optimizando cobertura y compensando descansos..."):
                        # Llamada al motor en logic.py
                        df_resultado = generar_malla_tecnica_pulp(
                            df_raw, n_map, d_map, 
                            m_cupo, a_cupo, b_cupo, 
                            f_i.year, f_i.month, 
                            dict_horarios
                        )
                    
                    if not df_resultado.empty:
                        st.session_state['temp_malla'] = df_resultado
                        st.session_state['rango_ref'] = rango
                        st.session_state['h_labels'] = {"T1": t1_h, "T2": t2_h, "T3": t3_h}
                        st.success("✅ Malla generada exitosamente.")
                    else:
                        st.error("No se pudo generar la malla. Verifique la base de datos de empleados.")
                else:
                    st.error("Por favor, seleccione un rango de fechas (Inicio y Fin).")

        with tab2:
            if 'temp_malla' in st.session_state:
                df_long = st.session_state['temp_malla']
                h_lab = st.session_state.get('h_labels', {})
                
                # --- VISTA HORIZONTAL (Pivot Table) ---
                # Usamos 'Dia' para columnas y 'Turno' para el contenido de la celda
                try:
                    df_horiz = df_long.pivot_table(
                        index=['Grupo', 'Empleado', 'Cargo'], 
                        columns='Dia', 
                        values='Turno', 
                        aggfunc='first'
                    ).reset_index()

                    st.subheader("🗓️ Cronograma General de Turnos")
                    st.caption(f"T1: {h_lab.get('T1')} | T2: {h_lab.get('T2')} | T3: {h_lab.get('T3')} | X: Apoyo/Disponible | D: Descanso")
                    
                    # Aplicación de Estilos
                    st.dataframe(df_horiz.style.map(estilo_malla), use_container_width=True, height=500)

                    # --- ACCIONES ---
                    col_down1, col_down2 = st.columns(2)
                    with col_down1:
                        if st.button("💾 GUARDAR EN HISTÓRICO", use_container_width=True):
                            f_i, f_f = st.session_state['rango_ref']
                            nueva_malla = pd.DataFrame([{
                                "Mes": f_i.strftime("%B %Y"),
                                "Rango": f"{f_i} a {f_f}",
                                "Fecha_Crea": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "Datos_JSON": df_long.to_json(orient='split'),
                                "Horarios": str(h_lab)
                            }])
                            df_h = read_db("historico_mallas")
                            if df_h is None: 
                                df_h = pd.DataFrame(columns=["Mes", "Rango", "Fecha_Crea", "Datos_JSON", "Horarios"])
                            
                            if save_db(pd.concat([df_h, nueva_malla], ignore_index=True), "historico_mallas"):
                                st.success("✅ Sincronizado en Base de Datos.")

                    with col_down2:
                        # Exportar a Excel
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_horiz.to_excel(writer, index=False, sheet_name='Malla')
                        st.download_button(
                            label="📥 DESCARGAR EXCEL",
                            data=output.getvalue(),
                            file_name=f"Malla_MovilGo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                except Exception as e:
                    st.error(f"Error al procesar la visualización: {e}")
            else:
                st.info("⚠️ No hay datos para mostrar. Configure los parámetros y genere la malla en la pestaña anterior.")

        with tab3:
            st.subheader("📜 Histórico de Programaciones")
            df_hist = read_db("historico_mallas")
            if df_hist is not None and not df_hist.empty:
                for i, row in df_hist.iloc[::-1].iterrows(): # Mostrar más recientes primero
                    with st.expander(f"📅 {row['Mes']} - (Creada: {row['Fecha_Crea']})"):
                        st.write(f"**Rango:** {row['Rango']}")
                        if st.button("Cargar esta Versión", key=f"load_h_{i}"):
                            st.session_state['temp_malla'] = pd.read_json(io.StringIO(row['Datos_JSON']), orient='split')
                            st.rerun()
            else:
                st.info("No se registran mallas anteriores.")

    # --- MÓDULO: BASE DE DATOS ---
    elif st.session_state['menu_actual'] == "👥 Base de Datos":
        st.header("👥 Gestión de Planta de Personal")
        
        # Filtros rápidos
        c_search, c_filter = st.columns([2, 1])
        search = c_search.text_input("🔍 Buscar técnico por nombre")
        role_filter = c_filter.selectbox("Filtrar por Cargo", ["TODOS", "MASTER", "TECNICO A", "TECNICO B"])
        
        df_display = df_raw.copy()
        if search:
            df_display = df_display[df_display['nombre'].str.contains(search.upper())]
        if role_filter != "TODOS":
            df_display = df_display[df_display['cargo'] == role_filter]

        st.dataframe(df_display, use_container_width=True)
        
        with st.expander("➕ Añadir Nuevo Técnico"):
            with st.form("add_tec"):
                n_name = st.text_input("Nombre Completo").upper()
                n_role = st.selectbox("Cargo", ["MASTER", "TECNICO A", "TECNICO B"])
                if st.form_submit_button("REGISTRAR"):
                    if n_name:
                        new_row = pd.DataFrame([{"nombre": n_name, "cargo": n_role}])
                        updated_db = pd.concat([df_raw, new_row], ignore_index=True)
                        save_db(updated_db, "empleados")
                        st.success(f"Técnico {n_name} registrado.")
                        st.rerun()
                    else:
                        st.warning("El nombre es obligatorio.")

    # --- MÓDULO: INICIO ---
    else:
        st.title("🏠 MovilGo Admin")
        st.markdown(f"""
        Bienvenido al sistema de gestión operativa.
        
        * **Técnicos en base de datos:** {len(df_raw)}
        * **Mallas en histórico:** {len(read_db('historico_mallas')) if read_db('historico_mallas') is not None else 0}
        
        Utilice el menú lateral para navegar entre las opciones.
        """)

if __name__ == "__main__":
    run_app()
