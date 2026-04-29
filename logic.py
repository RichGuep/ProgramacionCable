import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st
import io

@st.cache_data
def load_base():
    """Carga la base de datos de empleados."""
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        df['cargo'] = df['cargo'].astype(str).str.strip()
        df['nombre'] = df['nombre'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error al cargar empleados.xlsx: {e}")
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Preparación de personal
    c_list = []
    temp_df = df_raw.copy()
    for g_id, g_name in n_map.items():
        for cargo, req in zip(['Master', 'Tecnico A', 'Tecnico B'], [m_req, ta_req, tb_req]):
            matches = temp_df[temp_df['cargo'].str.contains(cargo, case=False)].head(req)
            for _, row in matches.iterrows():
                c_list.append({**row.to_dict(), "grupo": g_name})
            temp_df = temp_df.drop(matches.index)
    
    df_celulas = pd.DataFrame(c_list)
    grupos_nombres = list(n_map.values())
    g_rotan = [g for g in grupos_nombres if t_map.get(g) == "ROTA"]
    g_disp = next((g for g in grupos_nombres if t_map.get(g) == "DISP"), None)

    # 2. Configuración de tiempo
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = []
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        d_info.append({
            "n": d, "nom": DIAS_SEMANA[fecha.weekday()], 
            "sem_iso": fecha.isocalendar()[1],
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })
    semanas = sorted(list(set([d["sem_iso"] for d in d_info])))

    # 3. Motor de Turnos (PuLP)
    prob = LpProblem("Rotacion_Compensatoria", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    for s in semanas:
        for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
        for g in g_rotan: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
    for g in g_rotan:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]
    prob.solve(PULP_CBC_CMD(msg=0))
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

    # 4. Lógica de Compensación Correcta
    descansos_finales = {}
    stats_ley = {g: 0 for g in grupos_nombres} # Contador de descansos de ley disfrutados

    for idx_s, s in enumerate(semanas):
        dias_ocupados_semana = []
        
        # Ordenamos: los que menos han descansado en su día de ley tienen prioridad
        prioridad = sorted(grupos_nombres, key=lambda x: stats_ley[x])
        
        for g in prioridad:
            dia_pref = d_map.get(g)
            
            # SI le toca descansar su día de ley (Máximo 2 al mes para balancear)
            if dia_pref not in dias_ocupados_semana and stats_ley[g] < 2:
                descansos_finales[(g, s)] = (dia_pref, "DESC. LEY")
                dias_ocupados_semana.append(dia_pref)
                stats_ley[g] += 1
            else:
                # NO descansa su día de ley (TRABAJA), por lo tanto GANA un COMPENSATORIO
                # Buscamos un día entre semana para pagarle el sacrificio
                for dia_comp in ["Martes", "Miercoles", "Jueves"]:
                    if dia_comp not in dias_ocupados_semana:
                        descansos_finales[(g, s)] = (dia_comp, "DESC. COMPENSATORIO")
                        dias_ocupados_semana.append(dia_comp)
                        break

    # 5. Reconstrucción
    final_rows = []
    for d_i in d_info:
        s_iso = d_i["sem_iso"]
        quien_desc_hoy = [g for g in g_rotan if descansos_finales.get((g, s_iso), (None, ""))[0] == d_i["nom"]]
        
        t_disp = "T1"
        if g_disp:
            desc_disp = descansos_finales.get((g_disp, s_iso))
            if desc_disp and d_i["nom"] == desc_disp[0]:
                t_disp = desc_disp[1]
            elif quien_desc_hoy:
                t_disp = res_sem.get((quien_desc_hoy[0], s_iso), "T1")
            else:
                t_disp = "T1 (Apoyo)"

        for g_name in grupos_nombres:
            if g_name == g_disp: val = t_disp
            else:
                d_g = descansos_finales.get((g_name, s_iso))
                if d_g and d_i["nom"] == d_g[0]: val = d_g[1]
                else: val = res_sem.get((g_name, s_iso), "T1")

            h_str = ""
            tk = next((k for k in LISTA_TURNOS if k in str(val)), None)
            if tk and tk in horarios_dict:
                h = horarios_dict[tk]
                h_str = f"{h['inicio']} - {h['fin']}"

            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({
                    "Grupo": g_name, "Empleado": m['nombre'], "Cargo": m['cargo'],
                    "Horario": h_str, "Dia": d_i["label"], "Turno": val
                })

    return pd.DataFrame(final_rows)
