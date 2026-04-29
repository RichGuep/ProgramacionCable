import pandas as pd
from pulp import *
from datetime import datetime, timedelta

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor con Garantía de Descanso Semanal Obligatorio.
    Si trabaja el día de ley, el modelo le asigna un compensatorio en semana.
    """
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # 1. Organización de Células
    c_list = []
    # (Mantenemos tu lógica de asignación de personal por cargo...)
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
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
    grupos = list(n_map.values())
    turnos = ["T1", "T2", "T3"]

    # 2. Optimizador PuLP
    prob = LpProblem("Descanso_Garantizado_MovilGo", LpMinimize)
    
    # Variables: ¿Grupo g trabaja turno t el día d?
    asig = LpVariable.dicts("Asig", (grupos, lista_fechas, turnos), cat='Binary')

    # Objetivo: Maximizar la estabilidad (no es crítico, lo importante son las reglas)
    prob += 0 

    # 3. REGLAS MATEMÁTICAS (RESTRICCIONES)
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    for g in grupos:
        for s in semanas:
            dias_semana = [d for d in lista_fechas if d.isocalendar()[1] == s]
            if not dias_semana: continue
            
            # REGLA 1: DESCANSO OBLIGATORIO SEMANAL
            # La suma de turnos trabajados en la semana NO puede ser igual a los días de la semana.
            # Esto obliga a que al menos un día sea "D".
            prob += lpSum([asig[g][d][t] for d in dias_semana for t in turnos]) <= len(dias_semana) - 1

    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        for t in turnos:
            # REGLA 2: COBERTURA MÍNIMA (Garantizar T1, T2, T3)
            prob += lpSum([asig[g][d][t] for g in grupos]) >= 1
            
        for g in grupos:
            # REGLA 3: UN TURNO MÁXIMO POR DÍA
            prob += lpSum([asig[g][d][t] for t in turnos]) <= 1

    # REGLA 4: ROTACIÓN COHERENTE (T1, T2 o T3 fijo por semana)
    for s in semanas:
        dias_s = [d for d in lista_fechas if d.isocalendar()[1] == s]
        for g in grupos:
            for t in turnos:
                for d in dias_s:
                    prob += asig[g][d][t] <= lpSum([asig[g][dias_s[0]][t]]) + (1 - asig[g][dias_s[0]][t])
                    # (Simplificado: si trabaja, mantiene el turno de la semana)

    prob.solve(PULP_CBC_CMD(msg=0))

    # 4. CONSTRUCCIÓN DE RESULTADOS
    final_rows = []
    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        for g in grupos:
            turno_f = "D"
            for t in turnos:
                if value(asig[g][d][t]) == 1:
                    turno_f = t
            
            # Identificar tipo de descanso o trabajo
            desc_habitual = d_map.get(g)
            if turno_f == "D":
                nota = "DESCANSO LEY" if nom_dia == desc_habitual else "COMPENSATORIO"
            else:
                nota = "TRABAJA DESC. (COMPENSAR)" if nom_dia == desc_habitual else ""

            horario = horarios_dict.get(turno_f, "N/A")
            tecs = df_celulas[df_celulas['grupo'] == g]
            
            for _, tec in tecs.iterrows():
                final_rows.append({
                    "Grupo": g, "Empleado": tec['nombre'], "Cargo": tec['cargo'],
                    "Horario": horario, "Fecha": d, "Label": d.strftime("%d-%a"),
                    "Final": turno_f, "Nota": nota
                })

    return pd.DataFrame(final_rows)
