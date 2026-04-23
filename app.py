import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro - Sistema Integral", layout="wide", page_icon="🚌")

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
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception as e:
        st.error(f"Error al leer empleados.xlsx: {e}")
        return None

df_raw = load_base()

# Inicializar estados de sesión para auditoría
if 'df_final_base' not in st.session_state: st.session_state['df_final_base'] = pd.DataFrame()
if 'df_final_aux' not in st.session_state: st.session_state['df_final_aux'] = pd.DataFrame()

if df_raw is not None:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("📅 Periodo")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        st.divider()
        st.subheader("Planta Operativa")
        m_req = st.number_input("Masters p/g", 1, 5, 2)
        ta_req = st.number_input("Técnicos A p/g", 1, 15, 7)
        tb_req = st.number_input("Técnicos B p/g", 1, 10, 3)

    tab1, tab2, tab3 = st.tabs(["🏭 Planta T1-T2-T3", "👥 Auxiliares (10/10)", "🧐 Auditoría"])

    # --- TAB 1: PLANTA OPERATIVA ---
    with tab1:
        st.header("Malla Técnicos y Masters")
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        LISTA_TURNOS = ["T1", "T2", "T3"]
        
        with st.expander("📅 Grupos Base", expanded=True):
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    g_id = f"G{i+1}"
                    n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                    d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                    es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t_b_{i}")
                    n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

        if st.button("⚡ GENERAR PLANTA BASE"):
            g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
            num_dias = calendar.monthrange(ano_sel, mes_num)[1]
            d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
            semanas = sorted(list(set([d["sem"] for d in d_info])))

            # Optimizador PuLP
            prob = LpProblem("MovilGo_Rota", LpMinimize)
            asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
            prob += lpSum([(1 - asig[g][s][t]) for g in g_rotan for s in semanas for t in LISTA_TURNOS])
            for s in semanas:
                prob += lpSum([asig[g][s]["T3"] for g in g_rotan]) == 1
                for g in g_rotan: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            for g in g_rotan:
                for i in range(len(semanas)-1):
                    s1, s2 = semanas[i], semanas[i+1]
                    prob += asig[g][s1]["T3"] + asig[g][s2]["T1"] <= 0
                    prob += asig[g][s1]["T3"] + asig[g][s2]["T2"] <= 0
            prob.solve(PULP_CBC_CMD(msg=0))
            res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

            # Asignación de personal
            mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
            tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
            tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
            
            final_rows_base = []
            turno_vivo = {g: res_semanal.get((g, semanas[0]), "T1") for g in g_rotan}
            g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]

            for d_i in d_info:
                descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                for g in n_map.values():
                    if g == g_disp:
                        t_hoy = "T1" if not descansan_hoy else turno_vivo[descansan_hoy[0]]
                        if d_i["nom"] == d_map[g]: t_hoy = "DESC. LEY"
                    else:
                        t_hoy = "DESC. LEY" if d_i["nom"] == d_map[g] else turno_vivo[g]
                        if d_i["nom"] == d_map[g]: turno_vivo[g] = res_semanal.get((g, d_i["sem"]), turno_vivo[g])
                    
                    # Filtrar personas para el grupo
                    # (Aquí se asignan los empleados basándose en los cargos y requerimientos)
                    # Por simplicidad en este bloque completo, asignamos los labels:
                    final_rows_base.append({"Label": d_i["label"], "Grupo": g, "Turno": t_hoy, "Cargo": "Técnico/Master"})

            st.session_state['df_final_base'] = pd.DataFrame(final_rows_base)
            st.success("Planta Base Generada con éxito.")

    # --- TAB 2: AUXILIARES ---
    with tab2:
        st.header("Malla Auxiliares (10/10)")
        cargo_aux = "Auxiliar de Abordaje y Atención al Público"
        df_aux = df_raw[df_raw['cargo'].str.contains(cargo_aux, case=False, na=False)].copy()
        
        if not df_aux.empty:
            with st.expander("📅 Equipos Auxiliares", expanded=True):
                aux_n_map, aux_d_map = {}, {}
                cols_ax = st.columns(5)
                for i in range(5):
                    with cols_ax[i]:
                        n_eq = st.text_input(f"Eq {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                        d_eq = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                        aux_n_map[i] = n_eq; aux_d_map[n_eq] = d_eq

            if st.button("⚡ GENERAR AUXILIARES"):
                df_aux = df_aux.reset_index(drop=True)
                rows_aux = []
                for s_idx, sem in enumerate(semanas):
                    pool = ["T1", "T1", "T2", "T2", "DISP"]
                    turnos_sem = pool[-(s_idx % 5):] + pool[:-(s_idx % 5)]
                    for d_i in [d for d in d_info if d["sem"] == sem]:
                        for eq_idx in range(5):
                            eq_name = aux_n_map[eq_idx]
                            t_f = "DESC. LEY" if d_i["nom"] == aux_d_map[eq_name] else turnos_sem[eq_idx]
                            rows_aux.append({"Label": d_i["label"], "Grupo": eq_name, "Turno": t_f, "Cargo": cargo_aux})
                
                st.session_state['df_final_aux'] = pd.DataFrame(rows_aux)
                st.success("Auxiliares generados.")

    # --- TAB 3: AUDITORÍA ---
    with tab3:
        st.header("🧐 Auditoría de Cobertura Diaria")
        if not st.session_state['df_final_base'].empty or not st.session_state['df_final_aux'].empty:
            malla_total = pd.concat([st.session_state['df_final_base'], st.session_state['df_final_aux']])
            
            dia_audit = st.select_slider("Auditar día:", options=[d["label"] for d in d_info])
            df_dia = malla_total[malla_total['Label'] == dia_audit]
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Turnos Programados")
                for t in LISTA_TURNOS:
                    if t in df_dia['Turno'].values: st.success(f"Turno {t}: OK")
                    else: st.error(f"Turno {t}: FALTANTE")
            with c2:
                st.subheader("Conteo de Personal")
                st.write(df_dia.groupby(['Turno', 'Cargo']).size())
        else:
            st.info("Genere las mallas en las pestañas anteriores para ver la auditoría.")
