import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos: Lógica de Disponibilidad y Descansos")

# --- 1. CARGA DE DATOS ---
try:
    df_empleados = pd.read_excel("empleados.xlsx")
    df_empleados.columns = df_empleados.columns.str.strip().str.lower()
    
    col_nombre = next((c for c in df_empleados.columns if 'nombre' in c or 'empleado' in c), None)
    col_cargo = next((c for c in df_empleados.columns if 'cargo' in c), None)
    col_descanso = next((c for c in df_empleados.columns if 'descanso' in c), None)

    df_empleados[col_nombre] = df_empleados[col_nombre].astype(str).str.strip()
    df_empleados[col_cargo] = df_empleados[col_cargo].astype(str).str.strip()
    df_empleados[col_descanso] = df_empleados[col_descanso].astype(str).str.strip().str.lower()
except Exception as e:
    st.error(f"Error al leer Excel: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Cupos por Turno")
    cargos = df_empleados[col_cargo].unique()
    cupos = {c: st.number_input(f"Cupo {c}", value=2 if "master" in c.lower() else 7) for c in cargos}
    st.info("El sistema asignará 'DISPO' automáticamente a las personas que no estén en turno ni en descanso.")

# --- 3. MOTOR DE OPTIMIZACIÓN ---
if st.button("🚀 Generar Malla Mensual"):
    semanas = [1, 2, 3, 4]
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Planificacion_Corporativa", LpMinimize)
    
    # Variables: 1 si trabaja, 0 si no
    asig = LpVariable.dicts("Asig", (df_empleados[col_nombre], semanas, dias, turnos), cat='Binary')

    # A. CUMPLIMIENTO ESTRICTO DE CUPOS (2 por turno para Masters)
    for s in semanas:
        for d in dias:
            for t in turnos:
                for c in cargos:
                    emps_c = df_empleados[df_empleados[col_cargo] == c][col_nombre]
                    prob += lpSum([asig[e][s][d][t] for e in emps_c]) == cupos[c]

    # B. REGLAS DE DESCANSO Y DISPONIBILIDAD
    for _, row in df_empleados.iterrows():
        e = row[col_nombre]
        contrato = row[col_descanso]
        dia_fijo = "Sabado" if "sabado" in contrato else "Domingo"
        
        for s in semanas:
            # 1. Un solo turno al día
            for d in dias:
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1
            
            # 2. Trabajar exactamente 5 días a la semana (para que sobren 2 días de descanso/dispo)
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5

        # 3. Lógica del Fin de Semana (Mínimo 2 libres al mes en su día de contrato)
        prob += lpSum([asig[e][s][dia_fijo][t] for s in semanas for t in turnos]) <= 2

    # RESOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ Malla generada: 5 días de labor, 2 de descanso/gestión.")
        
        resultados = []
        for s in semanas:
            for d in dias:
                for e in df_empleados[col_nombre]:
                    turno_asignado = "DESCANSO"
                    # Verificar si trabaja
                    for t in turnos:
                        if value(asig[e][s][d][t]) == 1:
                            turno_asignado = t
                            break
                    
                    # Si no es descanso y no tiene turno, es DISPONIBILIDAD (Gestión)
                    # Aquí simulamos la lógica: el 1er día libre es DESCANSO, el 2do es DISPO
                    # Para simplificar la visualización:
                    resultados.append({"Semana": s, "Dia": d, "Empleado": e, "Turno": turno_asignado})

        df_res = pd.DataFrame(resultados)
        
        tabs = st.tabs([f"Semana {s}" for s in semanas])
        for i, s in enumerate(semanas):
            with tabs[i]:
                malla = df_res[df_res['Semana']==s].pivot(index='Empleado', columns='Dia', values='Turno')
                
                # Lógica para marcar DISPO: Si hay más de un DESCANSO a la semana, uno se vuelve DISPO
                def asignar_dispo(row):
                    descansos = [i for i, x in enumerate(row) if x == "DESCANSO"]
                    if len(descansos) > 1:
                        # El primer descanso de la semana se queda como DESCANSO
                        # El segundo se marca como DISPO (Gestión)
                        row.iloc[descansos[1]] = "DISPO"
                    return row
                
                malla_final = malla.apply(asignar_dispo, axis=1)
                st.dataframe(malla_final.reindex(columns=dias), use_container_width=True)
    else:
        st.error("❌ No se pudo balancear. Revisa los cupos.")
