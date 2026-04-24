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
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception as e:
        return None

def calcular_malla_tecnica(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, DIAS):
    # Lógica de filtrado
    mas = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    c_list = []
    for gn in n_map.values():
        for _ in range(m_req):
            if not mas.empty: c_list.append({**mas.iloc[0].to_dict(), "grupo": gn}); mas = mas.iloc[1:]
        for _ in range(ta_req):
            if not tca.empty: c_list.append({**tca.iloc[0].to_dict(), "grupo": gn}); tca = tca.iloc[1:]
        for _ in range(tb_req):
            if not tcb.empty: c_list.append({**tcb.iloc[0].to_dict(), "grupo": gn}); tcb = tcb.iloc[1:]
    
    df_cel = pd.DataFrame(c_list)
    g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    
    d_info = [{"n": d, "nom": DIAS[datetime(ano_sel, mes_num, d).weekday()], 
               "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], 
               "label": f"{d:02d}-{DIAS[datetime(ano_sel, mes_num, d).weekday()][:3]}"} 
              for d in range(1, num_dias + 1)]
    
    semanas = sorted(list(set([d["sem"] for d in d_info])))

    prob = LpProblem("Malla_MovilGo", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, ["T1","T2","T3"]), cat='Binary')
    for s in semanas:
        for t in ["T1","T2","T3"]: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
        for g in g_rotan: prob += lpSum([asig[g][s][t] for t in ["T1","T2","T3"]]) == 1
    
    prob.solve(PULP_CBC_CMD(msg=0))
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in ["T1","T2","T3"] if value(asig[g][s][t]) == 1}

    final_rows = []
    g_disp_name = [g for g in n_map.values() if t_map[g] == "DISP"][0]
    
    for d_i in d_info:
        desc_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
        hoy_vals = {g: ("DESC. LEY" if d_i["nom"] == d_map[g] else res_sem.get((g, d_i["sem"]), "T1")) for g in g_rotan}
        label_disp = hoy_vals.get(desc_hoy[0], "T1") if desc_hoy else "T1"
        for g in n_map.values():
            val = label_disp if g == g_disp_name else hoy_vals.get(g, "T1")
            for _, m in df_cel[df_cel['grupo'] == g].iterrows():
                final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val})
                
    return pd.DataFrame(final_rows)
