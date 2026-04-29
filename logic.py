import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st
import io

@st.cache_data
def load_base():
    """Carga la base de datos de empleados."""
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        return df
    except Exception as e:
        st.error(f"Error al cargar empleados.xlsx: {e}")
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict, alcance="Mes Completo", semana_inicio=1):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Preparación de Personal por Células
    c_list = []
    for g_id, g_name in n_map.items():
        temp_df = df_raw.copy()
        # Asignación simplificada por perfiles
        for cargo, req in zip(['Master', 'Tecnico A', 'Tecnico B'], [m_req, ta_req, tb_req]):
            matches = temp_df[temp_df['cargo'].str.contains(cargo, case=False)].head(req)
            for _, row in matches.iterrows():
                c_list.append({**row.to_dict(), "grupo": g_name})
            temp_df = temp_df.drop(matches.index)
    
    df_celulas = pd.DataFrame(c_list)
    grupos = list(n_map.values())
    
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
    dias_nums = [d["n"] for d in d_info]

    # 3. El Modelo PuLP
    prob = LpProblem("Optimizacion_Malla_Flexible", LpMaximize) # Maximizamos satisfacción de descanso

    # VARIABLES
    # asig: ¿El grupo g está asignado al turno t en la semana s?
    asig = LpVariable.dicts("Asig", (grupos, semanas, LISTA_TURNOS), cat='Binary')
    # trabaja: ¿El grupo g trabaja el día d? (1=Trabaja, 0=Descansa)
    trabaja = LpVariable.dicts("Trabaja", (grupos, dias_nums), cat='Binary')

    # FUNCIÓN OBJETIVO: Priorizar el descanso en el día preferido (d_map)
    # Si d_map[g] coincide con el día d, y trabaja[g][d] es 0, sumamos puntos.
    objetivo = []
    for g in grupos:
        pref = d_map[g]
        for d_i in d_info:
            if d_i["nom"] == pref:
                # Queremos que 'trabaja' sea 0 en su día preferido
                objetivo.append(1 - trabaja[g][d_i['n']])
    prob += lpSum(objetivo)

    # RESTRICCIONES
    for s in semanas:
        dias_de_sem = [d['n'] for d in d_info if d['sem_iso'] == s]
        
        for g in grupos:
            # 1. Cada grupo tiene exactamente 1 turno asignado por semana
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
            
            # 2. Derecho al descanso: Debe descansar al menos 1 día a la semana
            prob += lpSum([trabaja[g][d] for d in dias_de_sem]) <= len(dias_de_sem) - 1

        for t in LISTA_TURNOS:
            # 3. COBERTURA MÍNIMA: En cada turno, debe haber al menos 1 grupo trabajando
            for d in dias_de_sem:
                # Un grupo cubre el turno si está asignado a ese turno esa semana Y trabaja ese día
                prob += lpSum([asig[g][s][t] for g in grupos]) >= 1 # Asegura un grupo por turno
                
                # Relación entre asig y trabaja: si un grupo descansa, no cuenta para la cobertura
                # Esta es la parte clave: asegura que si alguien descansa, otro grupo asignado al mismo turno (si hubiera) 
                # o el sistema de apoyo deba cubrirlo.
                prob += lpSum([asig[g][s][t] * trabaja[g][d] for g in grupos]) >= 1

    # 4. Evitar rotaciones inhumanas (T3 -> T1)
    for g in grupos:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T3"] + asig[g][s2]["T1"] <= 1

    # RESOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    # 5. RECONSTRUCCIÓN DE RESULTADOS
    final_rows = []
    for d_i in d_info:
        d = d_i["n"]
        s = d_i["sem_iso"]
        
        for g in grupos:
            # Determinar qué turno tiene esta semana
            t_semanal = next((t for t in LISTA_TURNOS if value(asig[g][s][t]) == 1), "T1")
            
            # Determinar si hoy trabaja o descansa
            esta_trabajando = value(trabaja[g][d]) == 1
            
            estado_final = t_semanal if esta_trabajando else "DESC. COMPENSADO"
            if esta_trabajando and d_i["nom"] == d_map[g]:
                estado_final += " (Refuerzo)" # Trabajó en su día de descanso por necesidad

            # Horario
            h_str = ""
            if t_semanal in horarios_dict and esta_trabajando:
                h = horarios_dict[t_semanal]
                h_str = f"{h['inicio']} - {h['fin']}"

            # Filtrar empleados de este grupo
            miembros = df_celulas[df_celulas['grupo'] == g]
            for _, m in miembros.iterrows():
                final_rows.append({
                    "Grupo": g,
                    "Empleado": m['nombre'],
                    "Cargo": m['cargo'],
                    "Horario": h_str,
                    "Dia": d_i["label"],
                    "Turno/Estado": estado_final,
                    "n_dia": d
                })

    return pd.DataFrame(final_rows)

# --- INTERFAZ STREAMLIT (Resumida para ejecución) ---
st.title("Sistema de Mallas con Descanso Flotante")
df_base = load_base()

if df_base is not None:
    # Ejemplo de parámetros (Esto vendría de tus selectboxes en la UI)
    horarios = {
        "T1": {"inicio": "06:00", "fin": "14:00"},
        "T2": {"inicio": "14:00", "fin": "22:00"},
        "T3": {"inicio": "22:00", "fin": "06:00"}
    }
    
    # Simulación de mapas (esto lo llenas con tu UI actual)
    n_map = {1: "Grupo Alfa", 2: "Grupo Beta", 3: "Grupo Gamma", 4: "Grupo Delta"}
    d_map = {"Grupo Alfa": "Domingo", "Grupo Beta": "Domingo", "Grupo Gamma": "Sabado", "Grupo Delta": "Lunes"}
    t_map = {g: "ROTA" for g in n_map.values()}

    if st.button("Generar Malla Optimizada"):
        res = generar_malla_tecnica_pulp(df_base, n_map, d_map, t_map, 1, 1, 1, 2024, 5, horarios)
        
        # Mostrar Matriz
        pivot = res.pivot_table(index=['Grupo', 'Empleado'], columns='Dia', values='Turno/Estado', aggfunc='first')
        st.dataframe(pivot)
