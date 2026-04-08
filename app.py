import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos Mensual - Reforma Laboral")

# --- 1. CARGA Y LIMPIEZA DE DATOS ---
try:
    df_empleados = pd.read_excel("empleados.xlsx")
    df_empleados.columns = df_empleados.columns.str.strip().str.lower()
    
    col_nombre = next((c for c in df_empleados.columns if 'nombre' in c or 'empleado' in c), None)
    col_cargo = next((c for c in df_empleados.columns if 'cargo' in c), None)
    col_descanso = next((c for c in df_empleados.columns if 'descanso' in c), None)

    if not all([col_nombre, col_cargo, col_descanso]):
        st.error("❌ El Excel debe tener: Nombre, Cargo y Descanso.")
        st.stop()
    
    # Normalizar valores de cargos y descansos
    df_empleados[col_cargo] = df_empleados[col_cargo].str.strip()
    df_empleados[col_descanso] = df_empleados[col_descanso].str.strip().str.lower()

except Exception as e:
    st.error(f"❌ Error crítico: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN EN BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Parámetros de Operación")
    cargos = df_empleados[col_cargo].unique()
    cupos = {}
    for c in cargos:
        # Valores por defecto según tu lógica
        def_val = 2 if "master" in c.lower() else (7 if "a" in c.lower() else 3)
        cupos[c] = st.number_input(f"Cupo diario {c}", value=def_val)
    
    st.divider()
    st.info("Este modelo garantiza 2 días de descanso por semana y 2 fines de semana libres al mes.")

# --- 3. MOTOR DE OPTIMIZACIÓN (MENSUAL) ---
if st.button("🚀 Generar Programación Mensual Completa"):
    semanas = [1, 2, 3, 4]
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    # Definir problema
    prob = LpProblem("Planificacion_Mensual", LpMinimize)
    
    # Variable de decisión: x[empleado, semana, dia, turno]
    asig = LpVariable.dicts("Asig", (df_empleados[col_nombre], semanas, dias, turnos), cat='Binary')

    # A. CUMPLIMIENTO DE CUPOS DIARIOS
    for s in semanas:
        for d in dias:
            for t in turnos:
                for c in cargos:
                    emps_c = df_empleados[df_empleados[col_cargo] == c][col_nombre]
                    prob += lpSum([asig[e][s][d][t] for e in emps_c]) == cupos[c]

    # B. RESTRICCIONES POR EMPLEADO
    for _, row in df_empleados.iterrows():
        emp = row[col_nombre]
        contrato = row[col_descanso]
        
        # 1. Máximo un turno por día
        for s in semanas:
            for d in dias:
                prob += lpSum([asig[emp][s][d][t] for t in turnos]) <= 1
        
        # 2. Reforma Laboral: 2 días de descanso cada semana (5 días laborables)
        for s in semanas:
            prob += lpSum([asig[emp][s][d][t] for d in dias for t in turnos]) == 5
            
        # 3. Regla de Oro: Mínimo 2 fines de semana (Sab o Dom según contrato) libres al mes
        # Sumamos las veces que trabaja en su día contractual; debe ser <= 2
        dia_objetivo = "sabado" if "sabado" in contrato else "domingo"
        prob += lpSum([asig[emp][s][dia_objetivo][t] for s in semanas for t in turnos]) <= 2

    # RESOLVER
    with st.spinner("Calculando la mejor distribución mensual..."):
        prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ ¡Malla mensual generada con éxito!")
        
        # Consolidar resultados
        resultados = []
        for s in semanas:
            for d in dias:
                for t in turnos:
                    for e in df_empleados[col_nombre]:
                        if value(asig[e][s][d][t]) == 1:
                            resultados.append({
                                "Semana": s,
                                "Dia": d,
                                "Turno": t,
                                "Empleado": e,
                                "Cargo": df_empleados[df_empleados[col_nombre]==e][col_cargo].values[0]
                            })
        
        df_final = pd.DataFrame(resultados)
        
        # Visualización por semana
        for s in semanas:
            st.subheader(f"📅 Semana {s}")
            semana_df = df_final[df_final['Semana'] == s]
            malla = semana_df.pivot(index='Empleado', columns='Dia', values='Turno').fillna('---')
            st.dataframe(malla.reindex(columns=dias), use_container_width=True)
            
        st.download_button("📥 Descargar Reporte CSV", df_final.to_csv(index=False), "malla_mensual.csv")
    else:
        st.error("❌ No hay solución posible. Intenta bajar un cupo o revisar la cantidad de empleados.")
