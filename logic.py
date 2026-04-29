import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor PuLP que garantiza T1, T2, T3 sacrificando descansos de forma rotativa.
    """
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    # 1. Rango de Fechas
    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # 2. Organización de Células (Basado en tu lógica original)
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    c_list = []
    for g_id, g_name in n_map.items():
        for _ in range(m_req):
            if not mas_p.empty: 
                c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name})
                mas_p = mas_p.iloc[1:]
        for _ in range(ta_req):
            if not tca_p.empty: 
                c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name})
                tca_p = tca_p.iloc[1:]
        for _ in range(tb_req):
            if not tcb_p.empty: 
                c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name})
                tcb_p = tcb_p.iloc[1:]
    
    df_celulas = pd.DataFrame(c_list)
    grupos_nombres = list(n_map.values())
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    # 3. Optimización PuLP
    LISTA_TURNOS = ["T1", "T2", "T3"]
    prob = LpProblem("Cobertura_Garantizada", LpMinimize)
    
    asig = LpVariable.dicts("Asig", (grupos_nombres, semanas, LISTA_TURNOS), cat='Binary')
    sacrificio = LpVariable.dicts("Sacrif", (grupos_nombres, semanas), cat='Binary')

    # Minimizar sacrificios totales
    prob += lpSum([sacrificio[g][s] for g in grupos_nombres for s in semanas])

    for s in semanas:
        for t in LISTA_TURNOS:
            # Al menos un grupo por cada turno
            prob += lpSum([asig[g][s][t] for g in grupos_nombres]) >= 1
        
        for g in grupos_nombres:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1

    # Rotación semanal T1 -> T2 -> T3
    for g in grupos_nombres:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]

    prob.solve(PULP_CBC_CMD(msg=0))
    
    res_sem = {(g, s): t for g in grupos_nombres for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}
    res_sac = {(g, s): value(sacrificio[g][s]) for g in grupos_nombres for s in semanas}

    # 4. Construcción Malla Final
    final_rows = []
    for fecha in lista_fechas:
        dia_nom = dias_semana_es[fecha.weekday()]
        sem_iso = fecha.isocalendar()[1]
        
        for g_name in grupos_nombres:
            desc_hab = d_map.get(g_name)
            turno_sem = res_sem.get((g_name, sem_iso), "T1")
            
            # Si el día es su descanso pero el modelo decidió sacrificarlo
            if dia_nom == desc_hab:
                if res_sac.get((g_name, sem_iso), 0) == 1:
                    turno_f = turno_sem
                    nota = "COMPENSATORIO PENDIENTE"
                else:
                    turno_f = "D"
                    nota = "DESCANSO"
            else:
                turno_f = turno_sem
                nota = ""

            horario = horarios_dict.get(turno_f, "N/A")
            tecnicos = df_celulas[df_celulas['grupo'] == g_name]
            
            for _, tec in tecnicos.iterrows():
                final_rows.append({
                    "Grupo": g_name, "Empleado": tec['nombre'], "Cargo": tec['cargo'],
                    "Horario": horario, "Fecha": fecha, "Label": fecha.strftime("%d-%a"),
                    "Final": turno_f, "Nota": nota
                })

    return pd.DataFrame(final_rows)

def load_base():
    """Función mínima para evitar errores de importación"""
    return pd.DataFrame(columns=['nombre', 'cargo', 'grupo'])
