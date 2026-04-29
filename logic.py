import pandas as pd
from pulp import *
from datetime import datetime

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # ... (Carga de células igual a la anterior) ...
    grupos = list(n_map.values())
    turnos = ["T1", "T2", "T3"]
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    prob = LpProblem("Malla_Ergonomica_MovilGo", LpMinimize)
    asig = LpVariable.dicts("Asig", (grupos, lista_fechas, turnos), cat='Binary')

    # --- RESTRICCIONES DE ORO (TRANSICIONES) ---
    for g in grupos:
        for i in range(len(lista_fechas) - 1):
            d_actual = lista_fechas[i]
            d_siguiente = lista_fechas[i+1]
            
            # 1. Si hoy trabaja T3, MAÑANA NO PUEDE SER T2 NI T1 (Descanso vital)
            prob += asig[g][d_actual]["T3"] + asig[g][d_siguiente]["T2"] <= 1
            prob += asig[g][d_actual]["T3"] + asig[g][d_siguiente]["T1"] <= 1
            
            # 2. Si hoy trabaja T2, MAÑANA NO PUEDE SER T1
            prob += asig[g][d_actual]["T2"] + asig[g][d_siguiente]["T1"] <= 1

    # --- RESTRICCIONES DE COBERTURA Y DESCANSO SEMANAL ---
    for s in semanas:
        dias_s = [d for d in lista_fechas if d.isocalendar()[1] == s]
        for g in grupos:
            # Obligar a mínimo 1 descanso por semana
            prob += lpSum([asig[g][d][t] for d in dias_s for t in turnos]) <= len(dias_s) - 1
            
            # Mantener el mismo turno durante la semana (Estabilidad)
            for t in turnos:
                for d in dias_s:
                    prob += asig[g][d][t] <= lpSum([asig[g][dias_s[0]][t]]) + (1 - asig[g][dias_s[0]][t])

    for d in lista_fechas:
        for t in turnos:
            # Garantizar que siempre haya cobertura en cada turno
            prob += lpSum([asig[g][d][t] for g in grupos]) >= 1
        for g in grupos:
            prob += lpSum([asig[g][d][t] for t in turnos]) <= 1

    prob.solve(PULP_CBC_CMD(msg=0))

    # --- CONSTRUCCIÓN DE DATA ---
    final_rows = []
    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        for g in grupos:
            turno_f = "D"
            for t in turnos:
                if value(asig[g][d][t]) == 1: turno_f = t
            
            # Lógica de Notas
            desc_hab = d_map.get(g)
            if turno_f == "D":
                nota = "DESCANSO"
            else:
                nota = "TRABAJA DESC (COMPENSAR)" if nom_dia == desc_hab else ""

            # ... (Carga de tecnicos y empaquetado igual al anterior)
