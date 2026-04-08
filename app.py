import streamlit as st
import pandas as pd
from pulp import *

# Configuración de página
st.set_page_config(page_title="Programador de Turnos AI", layout="wide")

st.title("🗓️ Programador Automático de Personal")
st.markdown("""
Esta herramienta optimiza la asignación de turnos cumpliendo con los cupos requeridos, 
los descansos contractuales (Sábado/Domingo) y la reforma laboral.
""")

# --- 1. CONFIGURACIÓN DE PARÁMETROS ---
with st.sidebar:
    st.header("Configuración de Cupos")
    cupo_master = st.number_input("Cupo Técnico Master por turno", value=2)
    cupo_tecnico_a = st.number_input("Cupo Técnico A por turno", value=7)
    cupo_tecnico_b = st.number_input("Cupo Técnico B por turno", value=3)
    
    st.divider()
    st.header("Cargar Novedades")
    uploaded_file = st.file_uploader("Subir archivo de novedades (Excel/CSV)")

# --- 2. BASE DE DATOS SIMULADA (Esto podría venir de un Excel) ---
# Creamos la lista de empleados según tu imagen
empleados = (
    [{"id": f"M{i}", "cargo": "Master", "descanso": "Sabado" if i <= 4 else "Domingo"} for i in range(1, 9)] +
    [{"id": f"A{i}", "cargo": "Tecnico A", "descanso": "Sabado" if i <= 14 else "Domingo"} for i in range(1, 29)] +
    [{"id": f"B{i}", "cargo": "Tecnico B", "descanso": "Sabado" if i <= 6 else "Domingo"} for i in range(1, 13)]
)
df_empleados = pd.DataFrame(empleados)

# --- 3. GESTIÓN DE VACACIONES / INCAPACIDADES ---
st.subheader("🚩 Gestión de Ausencias")
col1, col2 = st.columns(2)
with col1:
    emp_ausente = st.selectbox("Seleccionar Empleado", df_empleados['id'].unique())
with col2:
    dias_ausente = st.multiselect("Días de Ausencia", ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"])

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button("🚀 Generar Programación de la Semana"):
    
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    cargos = ["Master", "Tecnico A", "Tecnico B"]
    cupos = {"Master": cupo_master, "Tecnico A": cupo_tecnico_a, "Tecnico B": cupo_tecnico_b}

    # Definir Problema
    prob = LpProblem("Turnos_Laborales", LpMinimize)

    # Variables de decisión
    asig = LpVariable.dicts("Asig", (df_empleados['id'], dias, turnos), cat='Binary')

    # RESTRICCIONES
    for d in dias:
        for t in turnos:
            for c in cargos:
                # 1. Cumplir con el cupo por cargo y turno
                emps_cargo = df_empleados[df_empleados['cargo'] == c]['id']
                prob += lpSum([asig[e][d][t] for e in emps_cargo]) == cupos[c]

    for e in df_empleados['id']:
        tipo_descanso = df_empleados[df_empleados['id'] == e]['descanso'].values[0]
        for d in dias:
            # 2. Máximo un turno al día
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # 3. Respetar descanso contractual (Sábado o Domingo)
            if d == tipo_descanso:
                prob += lpSum([asig[e][d][t] for t in turnos]) == 0
            
            # 4. Respetar Novedades (Vacaciones cargadas manualmente arriba)
            if e == emp_ausente and d in dias_ausente:
                prob += lpSum([asig[e][d][t] for t in turnos]) == 0

    # Resolver
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ ¡Programación generada con éxito!")
        
        # Formatear resultados para mostrar
        resultados = []
        for d in dias:
            for t in turnos:
                for e in df_empleados['id']:
                    if value(asig[e][d][t]) == 1:
                        resultados.append({"Dia": d, "Turno": t, "Empleado": e, "Cargo": df_empleados[df_empleados['id']==e]['cargo'].values[0]})
        
        df_res = pd.DataFrame(resultados)
        
        # Mostrar tabla pivotada (tipo malla)
        malla = df_res.pivot(index='Empleado', columns='Dia', values='Turno').fillna('-')
        st.dataframe(malla.reindex(columns=dias))
        
        # Botón para descargar
        st.download_button("📥 Descargar Excel", df_res.to_csv().encode('utf-8'), "turnos_semanales.csv", "text/csv")
    else:
        st.error("❌ No hay personal suficiente para cubrir los cupos con esas condiciones.")
