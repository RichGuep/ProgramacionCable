import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro - Sistema Integral de Mallas", layout="wide", page_icon="🚌")

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h2 style='text-align:center;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Acceso denegado")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        # Mapeo de columnas dinámico
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception as e:
        st.error(f"Error al cargar empleados.xlsx: {e}")
        return None

df_raw = load_base()

if df_raw is not None:
    # --- SIDEBAR GLOBAL ---
    with st.sidebar:
        st.header("📅 Periodo de Programación")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Seleccione Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Seleccione Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        
        st.divider()
        st.header("⚙️ Requerimientos Planta Base")
        m_req = st.number_input("Masters por Grupo", 1, 5, 2)
        ta_req = st.number_input("Técnicos A por Grupo", 1, 15, 7)
        tb_req = st.number_input("Técnicos B por Grupo", 1, 10, 3)

    # --- PESTAÑAS ---
    tab1, tab2 = st.tabs(["🏭 Planta Operativa (T1-T2-T3)", "👥 Auxiliares de Abordaje (10/10)"])

    # --- LÓGICA TAB 1: PLANTA OPERATIVA ---
    with tab1:
        st.header("Malla Técnicos y Masters (Regla de Oro T3)")
        num_g = 4
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        LISTA_TURNOS = ["T1", "T2", "T3"]

        with st.expander("📅 Configuración de Grupos Operativos", expanded=False):
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(num_g)
            for i in range(num_g):
                with cols[i]:
                    g_id = f"G{i+1}"
                    n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                    d_s = st.selectbox(f"Día Descanso", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                    es_disp = st.checkbox("¿Es Disponibilidad?", value=(i==3), key=f"t_b_{i}")
                    n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

        # Filtrar personal para planta base
        cargos_base = ['Master', 'Tecnico A', 'Tecnico B']
        df_base = df_raw[df_raw['cargo'].str.contains('|'.join(cargos_base), case=False, na=False)].copy()
        
        if st.button("⚡ GENERAR MALLA PLANTA OPERATIVA"):
            g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
            num_dias = calendar.monthrange(ano_sel, mes_num)[1]
            d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
            semanas = sorted(list(set([d["sem"] for d in d_info])))

            # Optimizador
            prob = LpProblem("MovilGo_PlantaBase", LpMinimize)
            asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
            prob += 0 # Objetivo neutro
            
            for s in semanas:
                prob += lpSum([asig[g][s]["T3"] for g in g_rotan]) == 1 # Único T3
                for g in g_rotan:
                    prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
            for g in g_rotan:
                for i in range(len(semanas)-1):
                    s1, s2 = semanas[i], semanas[i+1]
                    prob += asig[g][s1]["T3"] + asig[g][s2]["T1"] <= 1 # Evitar salto T3 a T1 sin descanso (simplificado)
            
            prob.solve(PULP_CBC_CMD(msg=0))
            res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

            # Construcción día a día
            final_rows_b = []
            g_disp_nom = [g for g in n_map.values() if t_map[g] == "DISP"][0]
            
            # (Simplificación de lógica de personal para el ejemplo)
            for d_i in d_info:
                for g in n_map.values():
                    t_hoy = res_semanal.get((g, d_i["sem"]), "T1") if t_map[g] == "ROTA" else "DISPONIBILIDAD"
                    if d_i["nom"] == d_map[g]: t_hoy = "DESC. LEY"
                    
                    # Asignar a empleados del grupo (Lógica Richard)
                    final_rows_b.append({"Label": d_i["label"], "Grupo": g, "Turno": t_hoy, "Día": d_i["n"]})

            st.success("Malla de Planta Base Generada.")
            st.info("Nota: Para ver el detalle por empleado, asegúrese de que su Excel tenga los cargos: Master, Tecnico A, Tecnico B.")

    # --- LÓGICA TAB 2: AUXILIARES DE ABORDAJE ---
    with tab2:
        st.header("Malla Auxiliares de Abordaje y Atención al Público")
        nombre_cargo_exacto = "Auxiliar de Abordaje y Atención al Público"
        df_aux = df_raw[df_raw['cargo'].str.contains(nombre_cargo_exacto, case=False, na=False)].copy()
        
        if df_aux.empty:
            st.warning(f"No se encontraron empleados con el cargo exacto: '{nombre_cargo_exacto}'")
        else:
            n_equipos_aux = 5
            personas_por_equipo = 5
            
            with st.expander("📅 Configuración de Equipos Auxiliares (25 personas)", expanded=True):
                aux_n_map, aux_d_map = {}, {}
                cols_aux = st.columns(n_equipos_aux)
                for i in range(n_equipos_aux):
                    with cols_aux[i]:
                        n_eq = st.text_input(f"Equipo {i+1}", f"EQ-AUX-{chr(65+i)}", key=f"aux_n_{i}")
                        d_eq = st.selectbox(f"Descanso Fijo", DIAS_SEMANA, index=i, key=f"aux_d_{i}")
                        aux_n_map[i] = n_eq
                        aux_d_map[n_eq] = d_eq

            if st.button("⚡ GENERAR MALLA AUXILIARES (10 T1 / 10 T2)"):
                df_aux = df_aux.reset_index(drop=True)
                # Dividir los 25 en los 5 equipos creados
                df_aux['equipo'] = [aux_n_map[i // personas_por_equipo] for i in range(len(df_aux))]
                
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info_aux = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas_aux = sorted(list(set([d["sem"] for d in d_info_aux])))
                
                rows_aux = []
                for s_idx, sem in enumerate(semanas_aux):
                    # Pool de turnos para cumplir 10 T1 y 10 T2 (2 equipos de 5 cada uno)
                    pool = ["T1", "T1", "T2", "T2", "DISPONIBILIDAD"]
                    # Rotación circular por semana
                    desplazamiento = s_idx % 5
                    turnos_semana = pool[-desplazamiento:] + pool[:-desplazamiento]
                    
                    for d_i in [d for d in d_info_aux if d["sem"] == sem]:
                        for eq_idx in range(n_equipos_aux):
                            eq_name = aux_n_map[eq_idx]
                            t_base = turnos_semana[eq_idx]
                            
                            # Si es su día de descanso parametrizado
                            final_t = t_base
                            if d_i["nom"] == aux_d_map[eq_name]:
                                final_t = "DESC. LEY"
                            
                            for _, emp in df_aux[df_aux['equipo'] == eq_name].iterrows():
                                rows_aux.append({
                                    "Equipo": eq_name,
                                    "Empleado": emp['nombre'],
                                    "Label": d_i["label"],
                                    "Turno": final_t,
                                    "Día": d_i["n"]
                                })
                
                df_final_aux = pd.DataFrame(rows_aux)
                piv_aux = df_final_aux.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                cols_ord = sorted(piv_aux.columns, key=lambda x: int(x.split('-')[0]))
                
                # Formato y Visualización
                def estilo_aux(v):
                    if v == "T1": return 'background-color: #dcfce7; color: #166534; border: 1px solid #b9f6ca'
                    if v == "T2": return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
                    if "DESC" in str(v): return 'background-color: #EF5350; color: white; font-weight: bold'
                    return 'background-color: #f3f4f6; color: #6b7280; font-style: italic'

                st.subheader("📋 Visualización de Turnos - Auxiliares")
                st.dataframe(piv_aux[cols_ord].style.applymap(estilo_aux), use_container_width=True)
                
                # Validación de Cobertura
                st.divider()
                st.subheader("📊 Resumen de Cobertura (Objetivo: 10 personas por turno)")
                audit = df_final_aux[df_final_aux['Turno'].isin(["T1", "T2"])].groupby(['Label', 'Turno']).size().unstack().fillna(0)
                st.table(audit.T)

# --- INSTRUCCIONES DE USO ---
with st.expander("ℹ️ Instrucciones de Configuración"):
    st.write("""
    1. **Archivo Excel:** Debe llamarse `empleados.xlsx` y estar en la misma carpeta que este script.
    2. **Cargos Planta Base:** Master, Tecnico A, Tecnico B.
    3. **Cargo Auxiliares:** Debe llamarse exactamente 'Auxiliar de Abordaje y Atención al Público'.
    4. **Equipos:** Los 25 auxiliares se dividen automáticamente en 5 equipos de 5 personas.
    """)
