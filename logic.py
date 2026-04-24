import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st

@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except: return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, estado_anterior=None):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # --- LOGICA ORIGINAL: Distribución por categorías ---
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    c_list = []
    for g_id, g_name in n_map.items():
        for _ in range(m_req):
            if not mas_p.empty: c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name}); mas_p = mas_p.iloc[1:]
        for _ in range(ta_req):
            if not tca_p.empty: c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name}); tca_p = tca_p.iloc[1:]
        for _ in range(tb_req):
            if not tcb_p.empty: c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name}); tcb_p = tcb_p.iloc[1:]
    
    df_celulas = pd.DataFrame(c_list)
    g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
    semanas = sorted(list(set([d["sem"] for d in d_info])))

    # --- LOGICA ORIGINAL: Optimizador PuLP ---
    prob = LpProblem("MovilGo_Rota", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    
    for s in semanas:
        for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
        for g in g_rotan: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
    
    for g in g_rotan:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]

    # --- LOGICA DE EMPALME: Continuidad ---
    if estado_anterior:
        s_ini = semanas[0]
        for g, ult_t in estado_anterior.items():
            if g in g_rotan:
                if "T3" in str(ult_t): prob += asig[g][s_ini]["T1"] == 0
                elif "T2" in str(ult_t): prob += asig[g][s_ini]["T3"] == 1

    prob.solve(PULP_CBC_CMD(msg=0))
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

    # --- REGLA DE ORO: Construcción con Disponibilidad y Bloqueos ---
    final_rows = []
    turno_vivo = {g: res_sem.get((g, semanas[0]), "T1") for g in g_rotan}
    g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]
    u_t_disp = "T1"

    for d_i in d_info:
        descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
        hoy_labels = {}
        for g in g_rotan:
            if d_i["nom"] == d_map[g]:
                hoy_labels[g] = "DESC. LEY"
                turno_vivo[g] = res_sem.get((g, d_i["sem"]), turno_vivo[g])
            else: hoy_labels[g] = turno_vivo[g]
        
        # --- Regla de Oro Disponibilidad ---
        if d_i["nom"] == d_map[g_disp]: l_disp = "DESC. LEY"
        else:
            if descansan_hoy:
                t_nec = turno_vivo[descansan_hoy[0]]
                if u_t_disp == "T3": l_disp = "APOYO (Post-Noche)"
                elif u_t_disp == "T2" and t_nec == "T1": l_disp = "T2 (Apoyo)"
                else: l_disp = t_nec
            else: l_disp = "T1" if u_t_disp != "T2" else "T2"
        
        if "DESC" not in l_disp and "APOYO" not in l_disp: u_t_disp = l_disp[:2]
        
        for g_id, g_name in n_map.items():
            val = l_disp if g_name == g_disp else hoy_labels.get(g_name, "T1")
            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({"Grupo": g_name, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Final": val})
    return pd.DataFrame(final_rows)
