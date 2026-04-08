import streamlit as st
import pandas as pd
from pulp import *

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Programador de Turnos AI", layout="wide")

st.title("🗓️ Programador Automático desde Excel")

# --- CARGA DE DATOS ---
# Intentamos leer el archivo local que subiste a Git
try:
    df_empleados = pd.read_excel("empleados.xlsx")
    st.success(f"✅ Se cargaron {len(df_empleados)} empleados desde el Excel.")
except Exception as e:
    st.error("❌ No se encontró el archivo 'empleados.xlsx'. Asegúrate de subirlo a GitHub.")
    st.stop()

# Mostrar una vista previa de tus empleados
with st.expander("Ver lista de empleados cargados"):
    st.write(df_empleados)

# --- CONFIGURACIÓN DE PARÁMETROS (Sidebar) ---
with st.sidebar:
    st.header("Cupos Requeridos")
    # Filtramos los cargos únicos que vienen de tu Excel para asignarles cupo
    cargos_en_excel = df_empleados['Cargo'].unique()
    cupos = {}
    for cargo in cargos_en_excel:
        cupos[cargo] = st.number_input(f"Cupo {cargo} por turno", value=2 if "Master" in cargo else 7)

# --- GESTIÓN DE NOVEDADES (Vacaciones/Incapacidades) ---
st.subheader("🚩 Registrar Ausencias Temporales")
col1, col2 = st.columns(2)
with col1:
    # Usamos la columna 'Nombre' de tu Excel
    emp_ausente = st.multiselect("Seleccionar Empleados ausentes", df_empleados['Nombre'].unique())
with col2:
    dias_ausente = st.multiselect("Días de Ausencia", ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"])

# --- BOTÓN PARA GENERAR ---
if st.button("🚀 Generar Programación"):
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]

    # Definir Problema
    prob = LpProblem("Turnos_Laborales", LpMinimize)

    # Variables de decisión: x[empleado, dia, turno]
    asig = LpVariable.dicts("Asig", (df_empleados['Nombre'], dias, turnos), cat='Binary')

    # --- RESTRICCIONES ---
    for d in dias:
        for t in turnos:
            for c in cargos_en_excel:
                # 1. Cumplir con el cupo por cargo y turno definido en el Excel
                emps_del_cargo = df_empleados[df_empleados['Cargo'] == c]['Nombre']
                prob += lpSum([asig[e][d][t] for e in emps_del_cargo]) == cupos[c]

    for _, row in df_empleados.iterrows():
        e = row['Nombre']
        dia_descanso_fijo = row['Descanso'] # Ej: "Sabado"
        
        for d in dias:
            # 2. Máximo un turno al día
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # 3. Respetar descanso contractual del Excel
            if d == dia_descanso_fijo:
                prob += lpSum([asig[e][d][t] for t in turnos]) == 0
            
            # 4. Respetar Novedades seleccionadas en la App
            if e in emp_ausente and d in dias_ausente:
                prob += lpSum([asig[e][d][t] for t in turnos]) == 0

    # Resolver
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ ¡Malla de turnos generada!")
        
        res_list = []
        for d in dias:
            for t in turnos:
                for e in df_empleados['Nombre']:
                    if value(asig[e][d][t]) == 1:
                        res_list.append({"Empleado": e, "Dia": d, "Turno": t})
        
        df_final = pd.DataFrame(res_list)
        malla_visual = df_final.pivot(index='Empleado', columns='Dia', values='Turno').fillna('-')
        st.dataframe(malla_visual.reindex(columns=dias))
        
        # Opción de descargar
        st.download_button("📥 Descargar Resultado", df_final.to_csv(index=False).encode('utf-8'), "programacion.csv")
    else:
        st.error("❌ Imposible generar: No hay suficiente personal para cubrir los cupos con esas ausencias.")
