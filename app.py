import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Modular", layout="wide")

st.title("🗓️ Programación por Cargo con Gestión de Disponibilidad")

# --- 1. CARGA DE DATOS ---
try:
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    # Identificar columnas dinámicamente
    col_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), None)
    col_car = next((c for c in df.columns if 'car' in c), None)
    col_des = next((c for c in df.columns if 'des' in c), None)

    # Limpieza
    df[col_nom] = df[col_nom].astype(str).str.strip()
    df[col_car] = df[col_car].astype(str).str.strip()
    df[col_des] = df[col_des].astype(str).str.strip().str.lower()
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

# --- 2. BARRA LATERAL (FILTROS) ---
with st.sidebar:
    st.header("🔍 Filtros de Programación")
    cargos_disponibles = sorted(df[col_car].unique())
    # BOTÓN DE FILTRO: Aquí indicas qué cargo quieres programar
    cargo_sel = st.selectbox("Seleccione el Cargo", cargos_disponibles)
    
    st.divider()
    st.header("⚙️ Parámetros")
    cupo_manual = st.number_input(f"Cupo por turno ({cargo_sel})", value=2 if "master" in cargo_sel.lower() else 7)
    
    # Info del personal
    total_cargo = len(df[df[col_car] == cargo_sel])
    st.info(f"Personal total: {total_cargo} técnicos.")
    st.write(f"Cupo total diario pedido: {cupo_manual * 3}")

# --- 3. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Programar {cargo_sel}"):
    df_f = df[df[col_car] == cargo_sel]
    semanas = [1, 2, 3, 4]
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    # Modelo de Maximización para evitar bloqueos
    prob = LpProblem("Planificacion_Modular", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], semanas, dias, turnos), cat='Binary')

    # OBJETIVO: Llenar la mayor cantidad de turnos posibles
    prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom] for s in semanas for d in dias for t in turnos])

    # RESTRICCIONES
    for s in semanas:
        for d in dias:
            for t in turnos:
                # El cupo es un límite máximo, si no hay gente, el modelo no se rompe
                prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e = row[col_nom]
        contrato = row[col_des]
        
        for s in semanas:
            for d in dias:
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1
            
            # Garantizar 5 días de labor para que queden 2 de descanso/dispo
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5

        # Regla de los 2 fines de semana libres según contrato
        dia_c = "Sabado" if "sabado" in contrato else "Domingo"
        prob += lpSum([asig[e][s][dia_c][t] for s in semanas for t in turnos]) <= 2

    # RESOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success(f"✅ Programación para {cargo_sel} generada.")
        
        # Procesar resultados
        res_list = []
        for s in semanas:
            for d in dias:
                for e in df_f[col_nom]:
                    t_asig = "DESCANSO"
                    for t in turnos:
                        if value(asig[e][s][d][t]) == 1:
                            t_asig = t
                    res_list.append({"Semana": s, "Dia": d, "Empleado": e, "Turno": t_asig})
        
        df_res = pd.DataFrame(res_list)
        
        # Mostrar por semanas
        tabs = st.tabs([f"Semana {s}" for s in semanas])
        for i, s in enumerate(semanas):
            with tabs[i]:
                malla = df_res[df_res['Semana'] == s].pivot(index='Empleado', columns='Dia', values='Turno')
                
                # Función para identificar DISPO (el segundo descanso de la semana)
                def aplicar_dispo(row):
                    descansos = [j for j, val in enumerate(row) if val == "DESCANSO"]
                    # Si hay 2 descansos, el que NO sea el del contrato lo marcamos como DISPO
                    if len(descansos) >= 2:
                        # Dejamos el primero como descanso y el segundo como disponibilidad
                        row.iloc[descansos[1]] = "DISPO"
                    return row

                malla_final = malla.apply(aplicar_dispo, axis=1)
                st.dataframe(malla_final.reindex(columns=dias), use_container_width=True)
                
                # Resumen de cobertura real
                st.subheader("📊 Cobertura por Turno")
                cols_cobertura = st.columns(7)
                for idx, d in enumerate(dias):
                    with cols_cobertura[idx]:
                        total_dia = (malla_final[d].isin(["AM", "PM", "Noche"])).sum()
                        st.metric(d, f"{total_dia}/{cupo_manual*3}")
    else:
        st.error(f"❌ No se pudo encontrar solución para {cargo_sel}. Revisa que el personal sea suficiente.")
