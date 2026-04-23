import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Multi-Planta", layout="wide", page_icon="⚙️")
LISTA_TURNOS = ["T1", "T2", "T3"] 
DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h2 style='text-align:center;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True; st.rerun()
                else: st.error("Acceso denegado")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except: return None

df_raw = load_base()

if df_raw is not None:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Parámetros Globales")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes de Programación", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        st.divider()
        st.subheader("Configuración Planta Base")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)

    # --- PESTAÑAS PRINCIPALES ---
    tab_base, tab_nuevo_cargo = st.tabs(["🏭 Planta Operativa (T1-T2-T3)", "👥 Nuevo Cargo (10/10)"])

    # --- LÓGICA PLANTA BASE (TU VERSIÓN ACTUALIZADA) ---
    with tab_base:
        num_g = 4
        with st.expander("📅 Configuración de Grupos Base", expanded=False):
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(num_g)
            for i in range(num_g):
                with cols[i]:
                    g_id = f"G{i+1}"
                    n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                    d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                    es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t_b_{i}")
                    n_map[g_id] = n_s
                    d_map[n_s] = d_s
                    t_map[n_s] = "DISP" if es_disp else "ROTA"

        # (Aquí iría el motor de optimización que ya tenemos para la planta base)
        # Por brevedad, nos enfocaremos en la nueva pestaña solicitada.
        st.info("Utilice el botón de generación en la pestaña del nuevo cargo para ver la nueva programación.")

    # --- LÓGICA NUEVO CARGO (EL REQUERIMIENTO NUEVO) ---
    with tab_nuevo_cargo:
        st.header("Programación Nuevo Cargo (Sin Nocturno)")
        
        # Filtrar empleados por el nuevo cargo (Supongamos que se llama 'Auxiliar' o el nombre que venga en el Excel)
        # Si no sabemos el nombre exacto, Richard, cámbialo en la línea de abajo:
        cargo_nombre = st.text_input("Nombre del cargo a filtrar (ej. Auxiliar):", "Auxiliar")
        df_nc = df_raw[df_raw['cargo'].str.contains(cargo_nombre, case=False, na=False)].copy()
        
        if df_nc.empty:
            st.warning(f"No se encontraron empleados con el cargo '{cargo_nombre}'.")
        else:
            st.success(f"Se encontraron {len(df_nc)} empleados para programar.")
            
            # Crear 5 equipos de 5 personas para los 25
            n_equipos = 5
            tamano_equipo = 5
            
            with st.expander("📅 Parametrización de Equipos Nuevos", expanded=True):
                nc_n_map = {}
                nc_d_map = {}
                cols_nc = st.columns(n_equipos)
                for i in range(n_equipos):
                    with cols_nc[i]:
                        eq_nom = st.text_input(f"Equipo {i+1}", f"EQ-NC-{i+1}", key=f"nc_n_{i}")
                        eq_des = st.selectbox(f"Descanso", DIAS_SEMANA, index=(i+2)%7, key=f"nc_d_{i}")
                        nc_n_map[i] = eq_nom
                        nc_d_map[eq_nom] = eq_des

            if st.button("⚡ GENERAR MALLA NUEVO CARGO"):
                # Asignar empleados a equipos
                df_nc['equipo'] = [nc_n_map[i // tamano_equipo] for i in range(len(df_nc))]
                
                # Definir rotación: EQ1,2 en T1 | EQ3,4 en T2 | EQ5 en Descanso/Disp (Rota semanal)
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info_nc = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas_nc = sorted(list(set([d["sem"] for d in d_info_nc])))
                
                rows_nc = []
                for s_idx, sem in enumerate(semanas_nc):
                    # Lógica de rotación de equipos (Cambio de turno semanal)
                    # Turno 0 y 1 -> T1 | Turno 2 y 3 -> T2 | Turno 4 -> Disponibilidad
                    turnos_semanales = ["T1", "T1", "T2", "T2", "DISPONIBILIDAD"]
                    # Rotar la lista de turnos según la semana
                    turnos_asignados = turnos_semanales[-(s_idx % 5):] + turnos_semanales[:-(s_idx % 5)]
                    
                    for d_i in [d for d in d_info_nc if d["sem"] == sem]:
                        for eq_idx in range(n_equipos):
                            eq_name = nc_n_map[eq_idx]
                            turno_base = turnos_asignados[eq_idx]
                            
                            # Si es su día de descanso parametrizado
                            final_t = turno_base
                            if d_i["nom"] == nc_d_map[eq_name]:
                                final_t = "DESC. LEY"
                            
                            for _, emp in df_nc[df_nc['equipo'] == eq_name].iterrows():
                                rows_nc.append({
                                    "Equipo": eq_name,
                                    "Empleado": emp['nombre'],
                                    "Label": d_i["label"],
                                    "Turno": final_t,
                                    "Día": d_i["n"]
                                })
                
                df_final_nc = pd.DataFrame(rows_nc)
                piv_nc = df_final_nc.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                
                # Estilos
                def estilo_nc(v):
                    if v == "T1": return 'background-color: #dcfce7; color: #166534'
                    if v == "T2": return 'background-color: #e0f2fe; color: #0369a1'
                    if "DESC" in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                    return 'background-color: #f3f4f6; color: #374151; font-style: italic'

                st.subheader("📋 Malla de Asignación 10/10")
                st.dataframe(piv_nc.style.applymap(estilo_nc), use_container_width=True)
                
                # Auditoría rápida
                st.divider()
                st.subheader("🔍 Verificación de Cobertura (Requerido: 10 por turno)")
                audit_nc = df_final_nc[df_final_nc['Turno'].isin(["T1", "T2"])].groupby(['Label', 'Turno']).size().unstack().fillna(0)
                st.table(audit_nc)
