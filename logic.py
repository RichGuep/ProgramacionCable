import pandas as pd
from pulp import *
from datetime import datetime

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor de Cobertura Forzada: Sacrifica descansos automáticamente para garantizar 
    los cupos de Masters, Tec A y Tec B en T1, T2 y T3 todos los días.
    """
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # 1. Organización de Células
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    c_list = []
    for g_id, g_name in n_map.items():
        for _ in range(m_req):
            if not mas_p.empty: 
                c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name, "tipo_rol": "M"})
                mas_p = mas_p.iloc[1:]
        for _ in range(ta_req):
            if not tca_p.empty: 
                c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name, "tipo_rol": "A"})
                tca_p = tca_p.iloc[1:]
        for _ in range(tb_req):
            if not tcb_p.empty: 
                c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name, "tipo_rol": "B"})
                tcb_p = tcb_p.iloc[1:]
    
    df_celulas = pd.DataFrame(c_list)
    grupos = list(n_map.values())
    turnos = ["T1", "T2", "T3"]
    roles = ["M", "A", "B"]

    # 2. Optimizador PuLP
    prob = LpProblem("Garantia_Total_MovilGo", LpMinimize)
    
    # Variables: ¿El grupo 'g' trabaja el turno 't' el día 'd'?
    asig = LpVariable.dicts("Asig", (grupos, lista_fechas, turnos), cat='Binary')
    # Variable de Sacrificio: ¿El grupo 'g' trabaja en su día de descanso?
    sacrif = LpVariable.dicts("Sacrif", (grupos, lista_fechas), cat='Binary')

    # Objetivo: Minimizar los sacrificios de descanso
    prob += lpSum([sacrif[g][d] for g in grupos for d in lista_fechas])

    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        
        for t in turnos:
            # REGLA CRÍTICA: Garantizar cupos mínimos por turno cada día
            # Al menos un grupo debe cubrir cada turno
            prob += lpSum([asig[g][d][t] for g in grupos]) >= 1
        
        for g in grupos:
            # Un grupo solo puede estar en un turno por día (o ninguno si descansa)
            prob += lpSum([asig[g][d][t] for t in turnos]) <= 1
            
            # Lógica de descanso habitual
            es_dia_descanso = (nom_dia == d_map.get(g))
            
            if es_dia_descanso:
                # Si es su descanso, la asignación a un turno implica un SACRIFICIO
                prob += lpSum([asig[g][d][t] for t in turnos]) <= sacrif[g][d]
            else:
                # Si NO es su descanso, DEBE estar en un turno (no puede descansar)
                prob += lpSum([asig[g][d][t] for t in turnos]) == 1

    # Regla de rotación semanal (para que no cambien de turno a mitad de semana)
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))
    for s in semanas:
        dias_de_la_semana = [d for d in lista_fechas if d.isocalendar()[1] == s]
        for g in grupos:
            for t in turnos:
                for d in dias_de_la_semana:
                    # Si el grupo está en un turno 't' un día de la semana, 
                    # debe estar en ese mismo 't' el resto de la semana que trabaje
                    prob += asig[g][d][t] <= lpSum([asig[g][dias_de_la_semana[0]][t]])

    prob.solve(PULP_CBC_CMD(msg=0))

    # 3. Construcción de resultados
    final_rows = []
    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        for g in grupos:
            turno_f = "D"
            for t in turnos:
                if value(asig[g][d][t]) == 1:
                    turno_f = t
            
            es_sacrificio = (nom_dia == d_map.get(g) and turno_f != "D")
            nota = "COMPENSATORIO PENDIENTE" if es_sacrificio else ""
            if turno_f == "D": nota = "DESCANSO"

            horario = horarios_dict.get(turno_f, "N/A")
            tecs = df_celulas[df_celulas['grupo'] == g]
            
            for _, tec in tecs.iterrows():
                final_rows.append({
                    "Grupo": g, "Empleado": tec['nombre'], "Cargo": tec['cargo'],
                    "Horario": horario, "Fecha": d, "Label": d.strftime("%d-%a"),
                    "Final": turno_f, "Nota": nota
                })

    return pd.DataFrame(final_rows)

def load_base():
    return pd.DataFrame(columns=['nombre', 'cargo', 'grupo'])
