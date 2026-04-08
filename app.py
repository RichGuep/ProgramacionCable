import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos Inteligente")
st.markdown("Prioriza estabilidad de turnos, descansos biológicos y cumplimiento de la reforma laboral.")

# --- 1. CARGA DE DATOS ---
try:
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    col_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), None)
    col_car = next((c for c in df.columns if 'car' in c), None)
    col_des = next((c for c in df.columns if 'des' in c), None)

    df[col_nom] = df[col_nom].astype(str).str.strip()
    df[col_car] = df[col_car].astype(str).str.strip()
    df[col_des] = df[col_des].astype(str).str.strip().str.lower()
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

# --- 2. FILTROS LATERALES ---
with st.sidebar:
    st.header("🔍 Panel de Control")
    cargos_disponibles = sorted(df[col_car].unique())
    cargo_sel = st.selectbox("Seleccione Cargo", cargos_disponibles)
    
    st.divider()
    cupo_manual = st.number_input(f"Cupo por turno ({cargo_sel})", value=2 if "master" in cargo_sel.lower() else 7)
    
    total_cargo = len(df[df[col_car] == cargo_sel])
    st.info(f"Personal disponible: {total_cargo}")

# --- 3. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Programación para {cargo_sel}"):
    df_f = df[df[col_car] == cargo_sel]
    semanas = [1, 2, 3, 4]
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Malla_Humana", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], semanas, dias, turnos), cat='Binary')

    # FUNCIÓN OBJETIVO: Maximizar cobertura
    prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom] for s in semanas for d in dias for t in turnos])

    # RESTRICCIONES
    for s in semanas:
        for d_idx, d in enumerate(dias):
            for t in turnos:
                # Cupos máximos
                prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom]]) <= cupo_manual

            # Restricciones por Empleado
            for _, row in df_f.iterrows():
                e = row[col_nom]
                
                # A. Solo un turno al día
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1
                
                # B. DESCANSO BIOLÓGICO: Si ayer hizo NOCHE, hoy NO puede hacer AM ni PM
                if d_idx > 0:
                    ayer = dias[d_idx - 1]
                    prob += asig[e][s][ayer]["Noche"] + asig[e][s][d]["AM"] <= 1
                    prob += asig[e][s][ayer]["Noche"] + asig[e][s][d]["PM"] <= 1
                
                # C. Transición de semanas (Noche de Domingo a AM de Lunes)
                if s > 1 and d == "Lunes":
                    prob += asig[e][s-1]["Domingo"]["Noche"] + asig[e][s]["Lunes"]["AM"] <= 1

        # D. Reforma: 5 días de labor por semana
        for _, row in df_f.iterrows():
            e = row[col_nom]
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5
            
            # E. Regla de Oro: 2 descansos contractuales al mes
            contrato = row[col_des]
            dia_c = "Sabado" if "sabado" in contrato else "Domingo"
            prob += lpSum([asig[e][s][dia_c][t] for s in semanas for t in turnos]) <= 2

    # RESOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success(f"✅ Programación para {cargo_sel} generada con criterios de descanso biológico.")
        
        # Procesamiento de resultados
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
        tabs = st.tabs([f"Semana {s}" for s in semanas])
        
        for i, s in enumerate(semanas):
            with tabs[i]:
                malla = df_res[df_res['Semana'] == s].pivot(index='Empleado', columns='Dia', values='Turno')
                
                # Lógica para DISPO (identificar el segundo día libre como Gestión)
                def asignar_dispo(row):
                    desc = [j for j, val in enumerate(row) if val == "DESCANSO"]
                    if len(desc) >= 2:
                        row.iloc[desc[1]] = "DISPO" # El segundo descanso se vuelve DISPO
                    return row

                malla_visual = malla.apply(asignar_dispo, axis=1)
                st.dataframe(malla_visual.reindex(columns=dias), use_container_width=True)
                
                # Métricas de cobertura
                st.subheader("📊 Cobertura Lograda")
                metrics = st.columns(7)
                for idx, d in enumerate(dias):
                    cob = (malla_visual[d].isin(["AM", "PM", "Noche"])).sum()
                    metrics[idx].metric(d, f"{cob}/{cupo_manual*3}")
    else:
        st.error("❌ No hay solución lógica. El personal es insuficiente para las reglas biológicas.")
