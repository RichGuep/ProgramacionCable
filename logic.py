import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st
import io

@st.cache_data
def load_base():
    """Carga la base de datos de empleados desde el Excel local."""
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

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict, alcance="Mes Completo", semana_inicio=1, estado_anterior=None):
    """Motor de optimización con lógica de alternancia de descansos (Zig-Zag)."""
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Asignación de personal a células
    c_list = []
    temp_df = df_raw.copy()
    for g_id, g_name in n_map.items():
        # Filtramos por perfiles técnicos
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
            "n": d, 
            "nom": DIAS_SEMANA[fecha.weekday()], 
            "sem_iso": fecha.isocalendar()[1],
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })
    semanas = sorted(list(set([d["sem_iso"] for d in d_info])))

    # 3. Motor de Turnos (PuLP)
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
    conflictos = {}
    for g, dia in d_map.items():
        if dia not in conflictos: conflictos[dia] = []
        conflictos[dia].append(g)

    descansos_finales = {}
    dias_compensados = ["Martes", "Miercoles", "Jueves"]

    for idx_s, s in enumerate(semanas):
        dias_ocupados_esta_semana = []
        
        # Primero procesamos los días que tienen conflictos (ej. dos grupos en Sábado)
        for dia_pref, grupos in conflictos.items():
            if len(grupos) > 1:
                # Alternamos el índice del grupo que recibe el "Descanso de Ley" según la semana
                lucky_idx = idx_s % len(grupos)
                for i, g in enumerate(grupos):
                    if i == lucky_idx:
                        descansos_finales[(g, s)] = (dia_pref, "DESC. LEY")
                        dias_ocupados_esta_semana.append(dia_pref)
                    else:
                        # Buscamos un día compensado libre
                        for dc in dias_compensados:
                            if dc not in dias_ocupados_esta_semana:
                                descansos_finales[(g, s)] = (dc, "DESC. COMPENSADO")
                                dias_ocupados_esta_semana.append(dc)
                                break
            else:
                # Caso sin conflicto
                g = grupos[0]
                descansos_finales[(g, s)] = (dia_pref, "DESC. LEY")
                dias_ocupados_esta_semana.append(dia_pref)

    # 5. Reconstrucción de la matriz final
    final_rows = []
    for d_i in d_info:
        # Identificamos quién descansa hoy de los grupos que rotan
        quien_descansa_hoy_ROTA = [g for g in g_rotan if descansos_finales.get((g, d_i["sem_iso"]), (None, ""))[0] == d_i["nom"]]
        
        # Turno del grupo de apoyo (DISP)
        t_disp = "T1"
        if g_disp:
            desc_disp = descansos_finales.get((g_disp, d_i["sem_iso"]))
            if desc_disp and d_i["nom"] == desc_disp[0]:
                t_disp = desc_disp[1]
            elif quien_descansa_hoy_ROTA:
                # El grupo DISP cubre al grupo que esté descansando hoy
                t_disp = res_sem.get((quien_descansa_hoy_ROTA[0], d_i["sem_iso"]), "T1")
            else:
                t_disp = "T1 (Apoyo)"

        for g_name in grupos_nombres:
            # Determinamos el valor del turno para este grupo en este día
            if g_name == g_disp:
                val = t_disp
            else:
                desc_g = descansos_finales.get((g_name, d_i["sem_iso"]))
                if desc_g and d_i["nom"] == desc_g[0]:
                    val = desc_g[1]
                else:
                    val = res_sem.get((g_name, d_i["sem_iso"]), "T1")

            # Determinamos el horario basado en el turno (T1, T2, T3)
            h_str = ""
            turno_key = next((tk for tk in LISTA_TURNOS if tk in val), None)
            if turno_key and turno_key in horarios_dict:
                h = horarios_dict[turno_key]
                h_str = f"{h['inicio']} - {h['fin']}"

            # Añadimos los datos de cada miembro del grupo a la lista final
            miembros = df_celulas[df_celulas['grupo'] == g_name]
            for _, m in miembros.iterrows():
                final_rows.append({
                    "Grupo": g_name, 
                    "Empleado": m['nombre'], 
                    "Cargo": m['cargo'],
                    "Horario": h_str, 
                    "Dia": d_i["label"], 
                    "Turno": val
                })

    return pd.DataFrame(final_rows)
