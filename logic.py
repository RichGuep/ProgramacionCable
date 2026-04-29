import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict, alcance="Mes Completo", semana_inicio=1, estado_anterior=None):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Asignación de personal a células
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

    # 3. Motor de Turnos (PuLP) - Rotación T1->T2->T3
    prob = LpProblem("Rotacion_Semanal", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    for s in semanas:
        for t in LISTA_TURNOS:
            prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
        for g in g_rotan:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
    for g in g_rotan:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]
    prob.solve(PULP_CBC_CMD(msg=0))
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

    # 4. Lógica de Alternancia de Descansos (Zig-Zag)
    # Agrupamos grupos por su día de descanso preferido
    conflictos = {}
    for g, dia in d_map.items():
        if dia not in conflictos: conflictos[dia] = []
        conflictos[dia].append(g)

    # Mapa final de descansos: (grupo, semana) -> dia_que_descansa
    descansos_finales = {}
    dias_compensados = ["Martes", "Miercoles", "Jueves"]

    for idx_s, s in enumerate(semanas):
        dias_ocupados_esta_semana = []
        
        for dia_pref, grupos in conflictos.items():
            if len(grupos) == 1:
                descansos_finales[(grupos[0], s)] = (dia_pref, "DESC. LEY")
                dias_ocupados_esta_semana.append(dia_pref)
            else:
                # Aquí ocurre la magia: Alternamos quién descansa el día de ley
                lucky_idx = idx_s % len(grupos) 
                for i, g in enumerate(grupos):
                    if i == lucky_idx:
                        descansos_finales[(g, s)] = (dia_pref, "DESC. LEY")
                        dias_ocupados_esta_semana.append(dia_pref)
                    else:
                        # Los demás se van a un día compensado que no esté usado
                        for dc in dias_compensados:
                            if dc not in dias_ocupados_esta_semana:
                                descansos_finales[(g, s)] = (dc, "DESC. COMPENSADO")
                                dias_ocupados_esta_semana.append(dc)
                                break

    # 5. Reconstrucción de la matriz
    final_rows = []
    for d_i in d_info:
        # ¿Quién descansa hoy (ROTA)?
        quien_descansa_hoy = [g for g in g_rotan if descansos_finales[(g, d_i["sem_iso"])][0] == d_i["nom"]]
        
        # Turno del grupo DISP
        t_disp = "T1"
        if g_disp:
            desc_disp = descansos_finales.get((g_disp, d_i["sem_iso"]))
            if d_i["nom"] == desc_disp[0]:
                t_disp = desc_disp[1]
            elif quien_descansa_hoy:
                # El DISP cubre al que esté de descanso (sea Ley o Compensado)
                t_disp = res_sem.get((quien_descansa_hoy[0], d_i["sem_iso"]), "T1")
            else:
                t_disp = "T1 (Apoyo)"

        for g_name in grupos_nombres:
            # Determinar Turno/Estado
            if g_name == g_disp:
                val = t_disp
            else:
                desc_g = descansos_finales[(g_name, d_i["sem_iso"])]
                if d_i["nom"] == desc_g[0]:
                    val = desc_g[1]
                else:
                    val = res_sem.get((g_name, d_i["sem_iso"]), "T1")

            # Horario
            h_str = ""
            turno_key = next((tk for tk in LISTA_TURNOS if tk in val), None)
            if turno_key and turno_key in horarios_dict:
                h = horarios_dict[turno_key]
                h_str = f"{h['inicio']} - {h['fin']}"

            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({
                    "Grupo": g_name, "Empleado": m['nombre'], "Cargo": m['cargo'],
                    "Horario": h_str, "Dia": d_i["label"], "Turno": val
                })

    return pd.DataFrame(final_rows)
