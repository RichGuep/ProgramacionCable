import pandas as pd
from pulp import *
from datetime import datetime, timedelta

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # Normalización de datos de técnicos
    df_raw.columns = [c.lower() for c in df_raw.columns]
    
    c_list = []
    for g_id, g_name in n_map.items():
        # (Lógica de filtrado de personal por cargo...)
        temp_m = df_raw[df_raw['cargo'].str.contains('MASTER', case=False)]
        # ... (aquí se asume la repartición de personal ya establecida)

    grupos = list(n_map.values())
    turnos = ["T1", "T2", "T3"]
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    prob = LpProblem("Malla_Optima_MovilGo", LpMinimize)
    
    # Variables de decisión
    asig = LpVariable.dicts("Asig", (grupos, lista_fechas, turnos), cat='Binary')
    trabaja_descanso = LpVariable.dicts("TrabDesc", (grupos, lista_fechas), cat='Binary')

    # Objetivo: Minimizar los cambios de turno innecesarios y cumplir descansos
    prob += lpSum([trabaja_descanso[g][d] for g in grupos for d in lista_fechas])

    for g in grupos:
        dia_ley = d_map.get(g)
        for s_idx, s in enumerate(semanas):
            dias_s = [d for d in lista_fechas if d.isocalendar()[1] == s]
            if not dias_s: continue

            # REGLA: 1 DESCANSO OBLIGATORIO POR SEMANA
            prob += lpSum([asig[g][d][t] for d in dias_s for t in turnos]) <= len(dias_s) - 1

            # REGLA: COMPENSACIÓN SEMANA SIGUIENTE
            if s_idx > 0:
                s_ant = semanas[s_idx - 1]
                dias_ant = [d for d in lista_fechas if d.isocalendar()[1] == s_ant]
                # Si trabajó su día de ley en la semana anterior, esta semana DEBE tener un compensatorio
                descanso_ant = [d for d in dias_ant if dias_semana_es[d.weekday()] == dia_ley]
                if descanso_ant:
                    d_ant = descanso_ant[0]
                    # Si trabajó el día de ley pasado, esta semana debe descansar al menos un día adicional (2 días total)
                    prob += lpSum([asig[g][d][t] for d in dias_s for t in turnos]) <= len(dias_s) - 1 - trabaja_descanso[g][d_ant]

    for d in lista_fechas:
        for t in turnos:
            # COBERTURA GARANTIZADA
            prob += lpSum([asig[g][d][t] for g in grupos]) >= 1
        for g in grupos:
            # UN SOLO TURNO POR DÍA
            prob += lpSum([asig[g][d][t] for t in turnos]) <= 1
            
            # Lógica de sacrificio de descanso
            nom_dia = dias_semana_es[d.weekday()]
            if nom_dia == d_map.get(g):
                prob += lpSum([asig[g][d][t] for t in turnos]) == trabaja_descanso[g][d]

    # REGLA: ROTACIÓN SEMANAL (T1 -> T2 -> T3)
    for g in grupos:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            d1_s = [d for d in lista_fechas if d.isocalendar()[1] == s1][0]
            d2_s = [d for d in lista_fechas if d.isocalendar()[1] == s2][0]
            # Encadenamiento: T1 -> T2, T2 -> T3, T3 -> T1
            prob += asig[g][d1_s]["T1"] <= asig[g][d2_s]["T2"] + (1 - asig[g][d2_s]["T2"]) # etc...

    prob.solve(PULP_CBC_CMD(msg=0))

    # Construcción de la respuesta final
    # ... (Misma lógica de empaquetado a DataFrame anterior)
    return pd.DataFrame(final_rows)
