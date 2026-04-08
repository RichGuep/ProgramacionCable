import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos Mensual - Reforma Laboral")

# --- 1. CARGA Y LIMPIEZA DE DATOS ---
try:
    df_empleados = pd.read_excel("empleados.xlsx")
    # Limpiar nombres de columnas
    df_empleados.columns = df_empleados.columns.str.strip().str.lower()
    
    col_nombre = next((c for c in df_empleados.columns if 'nombre' in c or 'empleado' in c), None)
    col_cargo = next((c for c in df_empleados.columns if 'cargo' in c), None)
    col_descanso = next((c for c in df_empleados.columns if 'descanso' in c), None)

    if not all([col_nombre, col_cargo, col_descanso]):
        st.error("❌ El Excel debe tener columnas: Nombre, Cargo y Descanso.")
        st.stop()
    
    # Limpiar contenido de las celdas
    df_empleados[col_nombre] = df_empleados[col_nombre].astype(str).str.strip()
    df_empleados[col_cargo] = df_empleados[col_cargo].astype(str).str.strip()
    df_empleados[col_descanso] = df_empleados[col_descanso].astype(str).str.strip().str.lower()

except Exception as e:
    st.error(f"❌ Error al leer el archivo: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Ajustes de Cupos")
    cargos = df_empleados[col_cargo].unique()
    cupos = {}
    for c in cargos:
        default = 2 if "master" in c.lower() else (7 if "a" in c.lower() else 3)
        cupos[c] = st.number_input(f"Cupo {c}", value=default)

# --- 3. MOTOR DE OPTIMIZACIÓN ---
if st.button("🚀 Generar Programación Mensual"):
    semanas = [1, 2, 3, 4]
    # Usamos nombres sin tildes y capitalizados para consistencia
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Planificacion_Mensual", LpMinimize)
    asig = LpVariable.dicts("Asig", (df_empleados[col_nombre], semanas, dias, turnos), cat='Binary')

    # A. RESTRICCIÓN DE CUPOS DIARIOS
    for s in semanas:
        for d in dias:
            for t in turnos:
                for c in cargos:
                    emps_c = df_empleados[df_empleados[col_cargo] == c][col_nombre]
                    prob += lpSum([asig[e][s][d][t] for e in emps_c]) == cupos[c]

    # B. RESTRICCIONES POR EMPLEADO
    for _, row in df_empleados.iterrows():
        emp = row[col_nombre]
        contrato = row[col_descanso] # Viene en minúsculas por la limpieza inicial
        
        # 1. Un turno al día máximo
        for s in semanas:
            for d in dias:
                prob += lpSum([asig[emp][s][d][t] for t in turnos]) <= 1
        
        # 2. Reforma Laboral: Trabajar 5 días a la semana (2 descansos)
        for s in semanas:
            prob += lpSum([asig[emp][s][d][t] for d in dias for t in turnos]) == 5
            
        # 3. Regla: Mínimo 2 Fines de Semana libres al mes (Garantía de descanso contractual)
        # Normalizamos la búsqueda del día contractual para que coincida con la lista 'dias'
        dia_objetivo = "Sabado" if "sabado" in contrato else "Domingo"
        
        # Suma de turnos en ese día específico durante el mes debe ser <= 2
        prob += lpSum([asig[emp][s][dia_objetivo][t] for s in semanas for t in turnos]) <= 2

    # --- RESOLVER ---
    with st.spinner("Optimizando malla mensual..."):
        prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ ¡Malla mensual generada correctamente!")
        
        resultados = []
        for s in semanas:
            for d in dias:
                for t in turnos:
                    for e in df_empleados[col_nombre]:
                        if value(asig[e][s][d][t]) == 1:
                            resultados.append({
                                "Semana": s, "Dia": d, "Turno": t, "Empleado": e,
                                "Cargo": df_empleados[df_empleados[col_nombre]==e][col_cargo].values[0]
                            })
        
        df_final = pd.DataFrame(resultados)
        
        # Visualización por pestañas para no saturar la pantalla
        tab1, tab2, tab3, tab4 = st.tabs(["Semana 1", "Semana 2", "Semana 3", "Semana 4"])
        tabs = [tab1, tab2, tab3, tab4]
        
        for i, s in enumerate(semanas):
            with tabs[i]:
                semana_df = df_final[df_final['Semana'] == s]
                if not semana_df.empty:
                    malla = semana_df.pivot(index='Empleado', columns='Dia', values='Turno').fillna('DESCANSO')
                    st.dataframe(malla.reindex(columns=dias), use_container_width=True)
        
        st.download_button("📥 Descargar Excel Mensual", df_final.to_csv(index=False).encode('utf-8'), "malla_mensual.csv")
    else:
        st.error("❌ No hay solución. Razones posibles: Tienes demasiados empleados con descanso el mismo día o los cupos superan tu personal disponible.")
