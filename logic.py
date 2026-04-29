import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import streamlit as st

@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        df['cargo'] = df['cargo'].astype(str).str.strip().str.upper()
        df['nombre'] = df['nombre'].astype(str).str.strip().str.upper()
        return df
    except Exception:
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Asignación de personal a grupos
    c_list = []
    temp_df = df_raw.copy()
    for g_id, g_name in n_map.items():
        for cargo, req in zip(['MASTER', 'TECNICO A', 'TECNICO B'], [m_req, ta_req, tb_req]):
            matches = temp_df[temp_df['cargo'].str.contains(cargo, case=False)].head(req)
            for _, row in matches.iterrows():
                c_list.append({**row.to_dict(), "grupo": g_name})
            temp_df = temp_df.drop(matches.index)
    
    df_celulas = pd.DataFrame(c_list)
    grupos = list(n_map.values())
    
    # 2. Tiempo
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = []
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        d_info.append({
            "n": d, 
            "nom": DIAS_SEMANA[fecha.weekday()], 
            "sem_iso": fecha.isocalendar()[1],
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })

    semanas = sorted(list(set([d["sem_iso"] for d in d_info])))
    dias_nums = [d["n"] for d in d_info]

    # 3. Optimización
    prob = LpProblem("Malla_MovilGo_Auto", LpMaximize)
    asig = LpVariable.dicts("Asig", (grupos, semanas, LISTA_TURNOS), cat='Binary')
    trabaja = LpVariable.dicts("Trabaja", (grupos, dias_nums), cat='Binary')
    activo = LpVariable.dicts("Activo", (grupos, dias_nums, LISTA_TURNOS), cat='Binary')

    # Objetivo: Respetar descansos preferidos
    obj = []
    for g in grupos:
        pref = d_map.get(g, "Domingo")
        for d_i in d_info:
            if d_i["nom"] == pref:
                obj.append(1 - trabaja[g][d_i['n']])
    prob += lpSum(obj)

    # Restricciones
    for s in semanas:
        d_sem = [d['n'] for d in d_info if d['sem_iso'] == s]
        for g in grupos:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) <= 1
            prob += lpSum([trabaja[g][d] for d in d_sem]) <= len(d_sem) - 1

        for d in d_sem:
            for t in LISTA_TURNOS:
                for g in grupos:
                    prob += activo[g][d][t] <= asig[g][s][t]
                    prob += activo[g][d][t] <= trabaja[g][d]
                    prob += activo[g][d][t] >= asig[g][s][t] + trabaja[g][d] - 1
                prob += lpSum([activo[g][d][t] for g in grupos]) >= 1

    # Evitar T3 -> T1
    for g in grupos:
        for i in range(len(semanas)-1):
            prob += asig[g][semanas[i]]["T3"] + asig[g][semanas[i+1]]["T1"] <= 1

    prob.solve(PULP_CBC_CMD(msg=0))

    # 4. Resultados con columnas consistentes
    final_rows = []
    for d_i in d_info:
        d, s = d_i["n"], d_i["sem_iso"]
        for g in grupos:
            t_asig = next((t for t in LISTA_TURNOS if value(asig[g][s][t]) == 1), None)
            is_working = value(trabaja[g][d]) == 1
            
            # Valor que irá a la celda del Excel/Streamlit
            val_final = t_asig if (is_working and t_asig) else ("X" if is_working else "D")
            
            # Horario dinámico
            h_data = horarios_dict.get(val_final, {"inicio": "", "fin": ""})
            h_str = f"{h_data['inicio']}-{h_data['fin']}" if h_data['inicio'] else ""

            miembros = df_celulas[df_celulas['grupo'] == g]
            for _, m in miembros.iterrows():
                final_rows.append({
                    "Grupo": g,
                    "Empleado": m['nombre'],
                    "Cargo": m['cargo'],
                    "Dia": d_i["label"], # ESTA COLUMNA ES LA QUE PIVOTAREMOS
                    "Turno": val_final,  # ESTE ES EL VALOR DE LA CELDA
                    "Horario": h_str
                })
                
    return pd.DataFrame(final_rows)
