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
    """Motor con Lógica de Compensación en la semana siguiente (T+1)."""
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

    # 3. Motor de Turnos (PuLP) - Mantiene rotación T1->T2->T3
    prob = LpProblem("Rotacion_Compensacion_Posterior", LpMinimize)
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

    # 4. Lógica de Descansos con Compensación POSTERIOR (Semana Siguiente)
    descansos_finales = {}
    deuda_compensatorio = {g: False for g in grupos_nombres} # Quién trabajó su descanso la semana anterior
    stats_ley = {g: 0 for g in grupos_nombres} # Cuántos fines de semana reales lleva descansados

    for idx_s, s in enumerate(semanas):
        dias_ocupados_esta_semana = []
        
        # PRIORIDAD 1: Los que tienen deuda de la semana anterior (Compensatorio Obligatorio)
        for g in grupos_nombres:
            if deuda_compensatorio[g]:
                for dia_c in ["Martes", "Miercoles", "Jueves"]: # Días entre semana
                    if dia_c not in dias_ocupados_esta_semana:
                        descansos_finales[(g, s)] = (dia_c, "DESC. COMPENSATORIO")
                        dias_ocupados_esta_semana.append(dia_c)
                        deuda_compensatorio[g] = False # Deuda pagada
                        break

        # PRIORIDAD 2: Asignar Descansos de Ley (Sábado/Domingo)
        # Ordenamos grupos para que rote quien descansa fin de semana
        prioridad_ley = sorted(grupos_nombres, key=lambda x: stats_ley[x])
        
        for g in prioridad_ley:
            # Si ya se le asignó un compensatorio por deuda arriba, no procesamos ley esta semana
            if (g, s) in descansos_finales: continue
            
            dia_pref = d_map.get(g)
            # Si el día de ley está libre y no ha excedido su cuota mensual de fines de semana (2)
            if dia_pref not in dias_ocupados_esta_semana and stats_ley[g] < 2:
                descansos_finales[(g, s)] = (dia_pref, "DESC. LEY")
                dias_ocupados_esta_semana.append(dia_pref)
                stats_ley[g] += 1
            else:
                # TRABAJA en su día de ley -> Genera DEUDA para la semana que viene
                deuda_compensatorio[g] = True

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
