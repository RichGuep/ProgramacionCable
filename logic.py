import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, extra_params):
    """
    Motor PuLP mejorado para rangos específicos y gestión de compensatorios.
    """
    # 1. Extraer parámetros del rango
    fecha_inicio = extra_params.get("inicio")
    fecha_fin = extra_params.get("fin")
    compensatorios = extra_params.get("compensatorios", {})
    horarios_dict = extra_params.get("horarios", {}) # Viene de st.session_state['horarios']

    # 2. Generar lista de días exacta del rango
    lista_fechas = pd.date_range(start=fecha_inicio, end=fecha_fin)
    dias_semana_es = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    
    # 3. Distribución de personal por células (Tu lógica original)
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
    g_rotan = [g for g in n_map.values() if t_map.get(g) == "ROTA"]
    semanas = sorted(list(set([f.isocalendar()[1] for f in lista_fechas])))

    # 4. Optimizador PuLP (Rotación Semanal)
    LISTA_TURNOS = ["T1", "T2", "T3"]
    prob = LpProblem("Optimizacion_MovilGo", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    
    for s in semanas:
        for t in LISTA_TURNOS:
            prob += lpSum([asig[g][s][t] for g in g_rotan]) >= 1
        for g in g_rotan:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
    # Restricción de rotación T1 -> T2 -> T3
    for g in g_rotan:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]

    prob.solve(PULP_CBC_CMD(msg=0))
    
    # Mapeo de resultados
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

    # 5. Construcción de la Malla Final
    final_rows = []
    for fecha in lista_fechas:
        dia_nom = dias_semana_es[fecha.weekday()]
        sem_iso = fecha.isocalendar()[1]
        label_dia = fecha.strftime("%d-%a")

        for g_id, g_name in n_map.items():
            descanso_hab = d_map.get(g_name)
            trabaja_descanso = compensatorios.get(g_name, False)
            
            # Determinar Turno base de la semana
            turno_base = res_sem.get((g_name, sem_iso), "T1")
            
            # Lógica de Descanso vs Trabajo
            if dia_nom == descanso_hab:
                if trabaja_descanso:
                    turno_final = turno_base
                else:
                    turno_final = "D"
            else:
                turno_final = turno_base

            # Obtener Horario Parametrizado
            horario_str = horarios_dict.get(turno_final, "N/A")

            # Asignar a cada técnico de la célula
            tecnicos_grupo = df_celulas[df_celulas['grupo'] == g_name]
            for _, tec in tecnicos_grupo.iterrows():
                final_rows.append({
                    "Grupo": g_name,
                    "Empleado": tec['nombre'],
                    "Cargo": tec['cargo'],
                    "Horario": horario_str,
                    "Fecha": fecha,
                    "Label": label_dia,
                    "Final": turno_final
                })

    return pd.DataFrame(final_rows)

def load_base():
    """Carga de seguridad por si falla el Excel o la DB"""
    return pd.DataFrame(columns=['nombre', 'cargo', 'grupo'])
