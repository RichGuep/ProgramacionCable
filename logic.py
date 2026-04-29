import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor PuLP que sacrifica descansos de forma rotativa para garantizar T1, T2 y T3.
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

    # 2. Optimizador PuLP
    LISTA_TURNOS = ["T1", "T2", "T3"]
    prob = LpProblem("Garantia_Cobertura_MovilGo", LpMinimize)
    
    # Variables de asignación: Grupo g, Semana s, Turno t
    asig = LpVariable.dicts("Asig", (grupos_nombres, semanas, LISTA_TURNOS), cat='Binary')
    # Variable de "Sacrificio": Indica si el grupo g debe trabajar su día de descanso en la semana s
    sacrificio = LpVariable.dicts("Sacrificio", (grupos_nombres, semanas), cat='Binary')

    # Objetivo: Minimizar los sacrificios totales y asegurar que se repartan (no siempre el mismo)
    prob += lpSum([sacrificio[g][s] for g in grupos_nombres for s in semanas])

    for s in semanas:
        # Regla 1: Garantizar que cada turno (T1, T2, T3) tenga al menos un grupo asignado
        for t in LISTA_TURNOS:
            prob += lpSum([asig[g][s][t] for g in grupos_nombres]) >= 1
        
        # Regla 2: Cada grupo solo puede tener un turno principal por semana
        for g in grupos_nombres:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1

    # Regla 3: Rotación T1 -> T2 -> T3 entre semanas
    for g in grupos_nombres:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]

    # Regla 4: No repetir sacrificio en semanas consecutivas para el mismo grupo (Equidad)
    for g in grupos_nombres:
        for i in range(len(semanas)-1):
            prob += sacrificio[g][semanas[i]] + sacrificio[g][semanas[i+1]] <= 1

    prob.solve(PULP_CBC_CMD(msg=0))
    
    # Mapeo de resultados del optimizador
    res_sem = {(g, s): t for g in grupos_nombres for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}
    res_sac = {(g, s): value(sacrificio[g][s]) for g in grupos_nombres for s in semanas}

    # 3. Construcción de la Malla
    final_rows = []
    for fecha in lista_fechas:
        dia_nom = dias_semana_es[fecha.weekday()]
        sem_iso = fecha.isocalendar()[1]
        
        for g_name in grupos_nombres:
            descanso_hab = d_map.get(g_name)
            turno_semanal = res_sem.get((g_name, sem_iso), "T1")
            debe_sacrificar = res_sac.get((g_name, sem_iso), 0)

            # Lógica de asignación final
            if dia_nom == descanso_hab:
                if debe_sacrificar == 1:
                    # El modelo decidió que este grupo trabaja su descanso para cubrir huecos
                    turno_final = turno_semanal
                    nota = "TRABAJA DESC."
                else:
                    turno_final = "D"
                    nota = "DESC. LEY"
            else:
                turno_final = turno_semanal
                nota = ""

            horario_str = horarios_dict.get(turno_final, "N/A")
            tecnicos_grupo = df_celulas[df_celulas['grupo'] == g_name]
            
            for _, tec in tecnicos_grupo.iterrows():
                final_rows.append({
                    "Grupo": g_name,
                    "Empleado": tec['nombre'],
                    "Cargo": tec['cargo'],
                    "Horario": horario_str,
                    "Fecha": fecha,
                    "Label": fecha.strftime("%d-%a"),
                    "Final": turno_final,
                    "Nota": nota
                })

    return pd.DataFrame(final_rows)
