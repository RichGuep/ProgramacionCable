import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Reforma 2026", layout="wide")

st.title("🗓️ Programación: Prioridad Descanso Contractual")

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
    st.error(f"Error: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Cupos Ideales")
    cargos = df_empleados[col_cargo].unique()
    cupos = {c: st.number_input(f"Cupo {c}", value=2 if "master" in c.lower() else 7) for c in cargos}

# --- 3. MOTOR DE OPTIMIZACIÓN ---
if st.button("🚀 Generar Malla Mensual"):
    semanas = [1, 2, 3, 4]
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    # Maximizamos la cobertura (llenar cupos) respetando restricciones
    prob = LpProblem("Reforma_Laboral", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_empleados[col_nombre], semanas, dias, turnos), cat='Binary')

    # FUNCIÓN OBJETIVO: Intentar llenar todos los cupos posibles
    prob += lpSum([asig[e][s][d][t] for e in df_empleados[col_nombre] for s in semanas for d in dias for t in turnos])

    # RESTRICCIONES
    for s in semanas:
        for d in dias:
            for t in turnos:
                for c in cargos:
                    emps_c = df_empleados[df_empleados[col_cargo] == c][col_nombre]
                    # Nunca exceder el cupo pedido
                    prob += lpSum([asig[e][s][d][t] for e in emps_c]) <= cupos[c]

    for _, row in df_empleados.iterrows():
        e = row[col_nombre]
        tipo_contrato = row[col_descanso] # 'sabado' o 'domingo'
        dia_contrato = "Sabado" if "sabado" in tipo_contrato else "Domingo"
        
        for s in semanas:
            # A. Solo un turno al día
            for d in dias:
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1
            
            # B. REFORMA: Trabajar exactamente 5 días (Descansar 2 obligatorios)
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5

            # C. REGLA 2/4: Mínimo 2 descansos en su día contractual al mes
            # Esto significa que como máximo puede trabajar 2 de los 4 días contractuales
            prob += lpSum([asig[e][s][dia_contrato][t] for s in semanas for t in turnos]) <= 2

    # RESOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ Malla generada respetando los 2 descansos contractuales al mes.")
        
        res = []
        for s in semanas:
            for d in dias:
                for t in turnos:
                    for e in df_empleados[col_nombre]:
                        if value(asig[e][s][d][t]) == 1:
                            res.append({"Semana": s, "Dia": d, "Turno": t, "Empleado": e})
        
        df_res = pd.DataFrame(res)
        tabs = st.tabs([f"Semana {s}" for s in semanas])
        for i, s in enumerate(semanas):
            with tabs[i]:
                malla = df_res[df_res['Semana']==s].pivot(index='Empleado', columns='Dia', values='Turno').fillna('---')
                st.dataframe(malla.reindex(columns=dias), use_container_width=True)
    else:
        st.error("No se encontró solución lógica. Revisa que el personal total (48) sea suficiente para la carga semanal.")
