import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Gestión Integral", layout="wide", page_icon="🚌")

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
        st.error(f"Error: No se pudo leer 'empleados.xlsx'. {e}")
        return None

df_raw = load_base()

if df_raw is not None:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("⚙️ Parámetros Globales")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        st.divider()
        st.subheader("Planta Operativa (T1-T3)")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)

    tab1, tab2 = st.tabs(["🏭 Planta Operativa (T1-T2-T3)", "👥 Auxiliares de Abordaje (10/10)"])

    # --- TAB 1: TÉCNICOS Y MASTERS (Lógica Original Restaurada) ---
    with tab1:
        st.header("Malla Técnicos y Masters")
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        LISTA_TURNOS = ["T1", "T2", "T3"]
        
        with st.expander("📅 Configuración de Grupos Operativos", expanded=True):
            n_map, d_map, t_map = {}, {}, {}
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    g_id = f"G{i+1}"
                    n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                    d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                    es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t_b_{i}")
                    n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

        if st.button("⚡ GENERAR MALLA TÉCNICOS/MASTERS"):
            # Lógica de distribución de personal
            mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
            tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
            tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
            
            c_list = []
            for g_id in n_map.keys():
                g_name = n_map[g_id]
                for _ in range(m_req):
                    if not mas_p.empty: c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name}); mas_p = mas_p.iloc[1:]
                for _ in range(ta_req):
                    if not tca_p.empty: c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name}); tca_p = tca_p.iloc[1:]
                for _ in range(tb_req):
                    if not tcb_p.empty: c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name}); tcb_p = tcb_p.iloc[1:]
            
            df_celulas = pd.DataFrame(c_list)
            
            # Optimizador de turnos
            g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
            num_dias = calendar.monthrange(ano_sel, mes_num)[1]
            d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
            semanas = sorted(list(set([d["sem"] for d in d_info])))

            prob = LpProblem("MovilGo_Rota", LpMinimize)
            asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
            prob += lpSum([(1 - asig[g][s][t]) for g in g_rotan for s in semanas for t in LISTA_TURNOS])
            
            for s in semanas:
                for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
                for g in g_rotan: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
            for g in g_rotan:
                for i in range(len(semanas)-1):
                    s1, s2 = semanas[i], semanas[i+1]
                    prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
                    prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]
                    prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            
            prob.solve(PULP_CBC_CMD(msg=0))
            res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

            # Construcción día a día con Regla de Oro
            final_rows = []
            turno_vivo = {g: res_semanal.get((g, semanas[0]), "T1") for g in g_rotan}
            g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]
            ultimo_turno_disp = "T1"

            for d_i in d_info:
                descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                hoy_labels = {}
                for g in g_rotan:
                    if d_i["nom"] == d_map[g]:
                        hoy_labels[g] = "DESC. LEY"
                        turno_vivo[g] = res_semanal.get((g, d_i["sem"]), turno_vivo[g])
                    else:
                        hoy_labels[g] = turno_vivo[g]
                
                # Regla Disponibilidad (Cubre T3 pero con bloqueos T3->T2/T1)
                if d_i["nom"] == d_map[g_disp]:
                    label_disp = "DESC. LEY"
                else:
                    if descansan_hoy:
                        g_a_cubrir = descansan_hoy[0]
                        t_necesario = turno_vivo[g_a_cubrir]
                        # Bloqueos de seguridad
                        if ultimo_turno_disp == "T3": label_disp = "APOYO (Post-Noche)"
                        elif ultimo_turno_disp == "T2" and t_necesario == "T1": label_disp = "T2 (Apoyo)"
                        else: label_disp = t_necesario
                    else: label_disp = "T1" if ultimo_turno_disp != "T2" else "T2"
                
                if "DESC" not in label_disp and "APOYO" not in label_disp: ultimo_turno_disp = label_disp[:2]

                for g in n_map.values():
                    val_final = label_disp if g == g_disp else hoy_labels[g]
                    for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                        final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Final": val_final, "Orden": d_i["n"]})

                df_f = pd.DataFrame(final_rows)
                piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                cols_ord = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))

            def estilo_b(v):
                v = str(v)
                if 'DESC' in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                if 'T3' in v: return 'background-color: #263238; color: white; font-weight: bold'
                if 'T1' in v: return 'background-color: #E3F2FD; color: #1565C0; border: 1px solid #166534'
                if 'T2' in v: return 'background-color: #FFF3E0; color: #EF6C00; border: 1px solid #0369a1'
                return 'color: gray; font-style: italic'

            st.dataframe(piv[cols_ord].style.map(estilo_b), use_container_width=True)

    # --- TAB 2: AUXILIARES (Lógica 10/10) ---
    with tab2:
        st.header("Malla Auxiliares de Abordaje y Atención al Público")
        cargo_aux = "Auxiliar de Abordaje y Atención al Público"
        df_aux = df_raw[df_raw['cargo'].str.contains(cargo_aux, case=False, na=False)].copy()
        
        if df_aux.empty:
            st.warning(f"No se encontró el cargo: {cargo_aux}")
        else:
            with st.expander("📅 Configurar Descansos Auxiliares", expanded=True):
                aux_n_map, aux_d_map = {}, {}
                cols_ax = st.columns(5)
                for i in range(5):
                    with cols_ax[i]:
                        n_eq = st.text_input(f"Equipo {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                        d_eq = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                        aux_n_map[i] = n_eq; aux_d_map[n_eq] = d_eq

            if st.button("⚡ GENERAR MALLA AUXILIARES"):
                df_aux = df_aux.reset_index(drop=True)
                df_aux['equipo'] = [aux_n_map[i // 5] for i in range(len(df_aux))]
                
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info_ax = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas_ax = sorted(list(set([d["sem"] for d in d_info_ax])))
                
                rows_ax = []
                for s_idx, sem in enumerate(semanas_ax):
                    pool = ["T1", "T1", "T2", "T2", "DISPONIBILIDAD"]
                    turnos_semana = pool[-(s_idx % 5):] + pool[:-(s_idx % 5)]
                    for d_i in [d for d in d_info_ax if d["sem"] == sem]:
                        for eq_idx in range(5):
                            eq_name = aux_n_map[eq_idx]
                            final_t = "DESC. LEY" if d_i["nom"] == aux_d_map[eq_name] else turnos_semana[eq_idx]
                            for _, emp in df_aux[df_aux['equipo'] == eq_name].iterrows():
                                rows_ax.append({"Equipo": eq_name, "Empleado": emp['nombre'], "Label": d_i["label"], "Turno": final_t})

                piv_ax = pd.DataFrame(rows_ax).pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                cols_ax_ord = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))

                def estilo_ax(v):
                    v = str(v)
                    if v == "T1": return 'background-color: #dcfce7; color: #166534'
                    if v == "T2": return 'background-color: #e0f2fe; color: #0369a1'
                    if "DESC" in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                    return 'background-color: #f3f4f6; color: #6b7280'

                st.dataframe(piv_ax[cols_ax_ord].style.map(estilo_ax), use_container_width=True)
