import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import streamlit as st

@st.cache_data
def load_base():
    """Carga la base de datos de empleados desde el Excel local."""
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        # Identificar columnas de nombre y cargo
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        # Limpieza de datos
        df['cargo'] = df['cargo'].astype(str).str.strip().str.upper()
        df['nombre'] = df['nombre'].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Error al cargar base de datos: {e}")
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict):
    """
    Motor de optimización automática. 
    Decide rotación de turnos y descansos compensados.
    """
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Organización de Células (Grupos)
    c_list = []
    temp_df = df_raw.copy()
    for g_id, g_name in n_map.items():
        for cargo, req in zip(['MASTER', 'TECNICO A', 'TECNICO B'], [m_req, ta_req, tb_req]):
            matches = temp_df[temp_df['cargo'].str.contains(cargo, case=False)].head(req)
            for _, row in matches.iterrows():
                c_list.append({**row.to_dict(), "grupo": g_name})
            temp_df = temp_df.drop(matches.index)
    
    df_celulas = pd.DataFrame(c_list)
    grupos = list(n_map.values())
    
    # 2. Configuración de Calendario
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
    dias_nums = [d["n"] for d in d_info]

    # 3. Creación del Problema de Optimización
    prob = LpProblem("Malla_MovilGo_Automatica", LpMaximize)

    # VARIABLES DE DECISIÓN
    # asig: El grupo g tiene el turno t en la semana s
    asig = LpVariable.dicts("Asig", (grupos, semanas, LISTA_TURNOS), cat='Binary')
    # trabaja: El grupo g trabaja el día d (1=Trabaja, 0=Descansa)
    trabaja = LpVariable.dicts("Trabaja", (grupos, dias_nums), cat='Binary')
    # activo: Variable auxiliar (asig AND trabaja) para cobertura
    activo = LpVariable.dicts("Activo", (grupos, dias_nums, LISTA_TURNOS), cat='Binary')

    # FUNCIÓN OBJETIVO
    # Prioridad 1: Que la gente trabaje (cobertura)
    obj_trabajo = lpSum([trabaja[g][d] for g in grupos for d in dias_nums])
    # Prioridad 2: Que el descanso sea en el día preferido
    preferencias = []
    for g in grupos:
        pref = d_map.get(g, "Domingo")
        for d_i in d_info:
            if d_i["nom"] == pref:
                preferencias.append(1 - trabaja[g][d_i['n']])
    
    # Maximizamos trabajo y satisfacción de descanso (la preferencia tiene peso extra)
    prob += (obj_trabajo * 1) + (lpSum(preferencias) * 10)

    # RESTRICCIONES
    for s in semanas:
        d_sem = [d['n'] for d in d_info if d['sem_iso'] == s]
        for g in grupos:
            # Cada grupo tiene un turno asignado por semana
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
            # REGLA DE ORO: Exactamente 1 descanso por semana
            # Esto obliga a trabajar 6 días y descansar 1
            prob += lpSum([trabaja[g][d] for d in d_sem]) == (len(d_sem) - 1)

        for d in d_sem:
            for t in LISTA_TURNOS:
                for g in grupos:
                    # Restricciones de linearización para 'activo'
                    prob += activo[g][d][t] <= asig[g][s][t]
                    prob += activo[g][d][t] <= trabaja[g][d]
                    prob += activo[g][d][t] >= asig[g][s][t] + trabaja[g][d] - 1
                
                # COBERTURA: Al menos 1 grupo debe estar presente por turno y día
                prob += lpSum([activo[g][d][t] for g in grupos]) >= 1

    # ERGONOMÍA: Evitar Turno 3 (Noche) y entrar en Turno 1 (Mañana) la siguiente semana
    for g in grupos:
        for i in range(len(semanas)-1):
            prob += asig[g][semanas[i]]["T3"] + asig[g][semanas[i+1]]["T1"] <= 1

    # Ejecutar Solver
    prob.solve(PULP_CBC_CMD(msg=0))

    # 4. Construcción de la Tabla de Resultados
    final_rows = []
    if LpStatus[prob.status] != 'Optimal':
        # Si no hay solución óptima, intentamos relajar la restricción de descanso (opcional)
        st.warning("Advertencia: El sistema no encontró una solución perfecta. Verifique la cantidad de grupos.")

    for d_i in d_info:
        d, s = d_i["n"], d_i["sem_iso"]
        for g in grupos:
            # Obtener turno asignado en la semana
            t_semanal = next((t for t in LISTA_TURNOS if value(asig[g][s][t]) == 1), None)
            # Verificar si trabaja hoy
            labora_hoy = value(trabaja[g][d]) == 1
            
            # Determinación de etiqueta
            if not labora_hoy:
                val_final = "D" # Descanso
            elif t_semanal:
                val_final = t_semanal
            else:
                val_final = "X" # Apoyo/Disponible

            # Obtener horario del diccionario
            h_data = horarios_dict.get(val_final, {"inicio": "", "fin": ""})
            h_str = f"{h_data['inicio']}-{h_data['fin']}" if labora_hoy and h_data['inicio'] else ""

            # Replicar a todos los empleados del grupo
            miembros = df_celulas[df_celulas['grupo'] == g]
            for _, m in miembros.iterrows():
                final_rows.append({
                    "Grupo": g,
                    "Empleado": m['nombre'],
                    "Cargo": m['cargo'],
                    "Dia": d_i["label"],
                    "Turno": val_final,
                    "Horario": h_str
                })
                
    return pd.DataFrame(final_rows)
