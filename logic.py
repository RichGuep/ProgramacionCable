import pandas as pd
from pulp import *
from datetime import datetime

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor PuLP: Garantiza T1, T2, T3 y obliga a un descanso semanal (Ley).
    """
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    horarios_dict = extra_params.get("horarios", {})

    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # Normalizar cargos
    df_raw.columns = [c.lower() for c in df_raw.columns]
    mas_p = df_raw[df_raw['cargo'].str.contains('MASTER', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('TECNICO A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('TECNICO B', case=False)].copy()
    
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
    grupos = list(n_map.values())
    turnos = ["T1", "T2", "T3"]

    prob = LpProblem("Planificacion_Automatica", LpMinimize)
    asig = LpVariable.dicts("Asig", (grupos, lista_fechas, turnos), cat='Binary')

    # --- RESTRICCIONES ---
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    for g in grupos:
        for s in semanas:
            dias_s = [d for d in lista_fechas if d.isocalendar()[1] == s]
            if not dias_s: continue
            # LEY: Al menos un día de descanso por semana (Máximo días-1 trabajados)
            prob += lpSum([asig[g][d][t] for d in dias_s for t in turnos]) <= len(dias_s) - 1

    for d in lista_fechas:
        for t in turnos:
            # COBERTURA: Siempre debe haber alguien en T1, T2 y T3
            prob += lpSum([asig[g][d][t] for g in grupos]) >= 1
        for g in grupos:
            prob += lpSum([asig[g][d][t] for t in turnos]) <= 1

    prob.solve(PULP_CBC_CMD(msg=0))

    final_rows = []
    for d in lista_fechas:
        nom_dia = dias_semana_es[d.weekday()]
        for g in grupos:
            turno_f = "D"
            for t in turnos:
                if value(asig[g][d][t]) == 1: turno_f = t
            
            desc_hab = d_map.get(g)
            if turno_f == "D":
                nota = "DESCANSO LEY" if nom_dia == desc_hab else "COMPENSATORIO"
            else:
                nota = "TRABAJA DESC (COMPENSAR)" if nom_dia == desc_hab else ""

            tecs = df_celulas[df_celulas['grupo'] == g]
            for _, tec in tecs.iterrows():
                final_rows.append({
                    "Grupo": g, "Empleado": tec['nombre'], "Cargo": tec['cargo'],
                    "Horario": horarios_dict.get(turno_f, "N/A"), "Fecha": d, 
                    "Label": d.strftime("%d-%a"), "Final": turno_f, "Nota": nota
                })
    return pd.DataFrame(final_rows)
