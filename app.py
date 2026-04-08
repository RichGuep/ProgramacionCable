import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos: Auditoría de Personal y Operación")

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
    st.error(f"Error al leer el archivo: {e}"); st.stop()

# --- 2. FILTROS ---
with st.sidebar:
    st.header("🔍 Panel de Control")
    cargo_sel = st.selectbox("Seleccione Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input(f"Cupo por turno", value=2 if "master" in cargo_sel.lower() else 7)
    st.info(f"Personal: {len(df[df[col_car] == cargo_sel])}")

# --- 3. MOTOR ---
if st.button(f"🚀 Generar Programación y Métricas"):
    df_f = df[df[col_car] == cargo_sel]
    semanas, dias, turnos = [1, 2, 3, 4], ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"], ["AM", "PM", "Noche"]
    
    prob = LpProblem("Malla_Auditada", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], semanas, dias, turnos), cat='Binary')

    # Función Objetivo: Maximizar cobertura
    prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom] for s in semanas for d in dias for t in turnos])

    for s in semanas:
        for d_idx, d in enumerate(dias):
            for t in turnos:
                prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom]]) <= cupo_manual
            for e in df_f[col_nom]:
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1
                if d_idx > 0: # Descanso Biológico
                    prob += asig[e][s][dias[d_idx-1]]["Noche"] + asig[e][s][d]["AM"] <= 1
                    prob += asig[e][s][dias[d_idx-1]]["Noche"] + asig[e][s][d]["PM"] <= 1

    for _, row in df_f.iterrows():
        e = row[col_nom]
        for s in semanas:
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5
        
        dia_c = "Sabado" if "sabado" in row[col_des] else "Domingo"
        prob += lpSum([asig[e][s][dia_c][t] for s in semanas for t in turnos]) <= 2

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        res_list = []
        for s in semanas:
            for d in dias:
                for e in df_f[col_nom]:
                    t_asig = "DESCANSO"
                    for t in turnos:
                        if value(asig[e][s][d][t]) == 1: t_asig = t
                    res_list.append({"Semana": s, "Dia": d, "Empleado": e, "Turno": t_asig, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]})
        
        df_res = pd.DataFrame(res_list)
        st.success(f"✅ Programación Mensual: {cargo_sel}")

        # --- TABS DE VISUALIZACIÓN ---
        tab_malla, tab_auditoria_emp, tab_auditoria_cupo = st.tabs(["📅 Malla Mensual", "👤 Auditoría Empleados", "🏭 Cobertura Operativa"])

        with tab_malla:
            for s in semanas:
                st.subheader(f"Semana {s}")
                malla = df_res[df_res['Semana'] == s].pivot(index='Empleado', columns='Dia', values='Turno')
                st.dataframe(malla.reindex(columns=dias), use_container_width=True)

        with tab_auditoria_emp:
            st.header("📊 Auditoría de Descansos por Empleado")
            met_emp = []
            for e in df_f[col_nom]:
                data_e = df_res[df_res['Empleado'] == e]
                dia_c = "Sabado" if "sabado" in data_e['Contrato'].iloc[0] else "Domingo"
                libres = len(data_e[(data_e['Dia'] == dia_c) & (data_e['Turno'] == 'DESCANSO')])
                comp = len(data_e[(data_e['Dia'].isin(["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"])) & (data_e['Turno'] == 'DESCANSO')])
                met_emp.append({"Empleado": e, "Día Contrato": dia_c, "Fines de Semana Libres": f"{libres}/4", "Compensatorios L-V": comp})
            st.table(pd.DataFrame(met_emp))

        with tab_auditoria_cupo:
            st.header("🏭 Cumplimiento de Cupos por Turno")
            st.write(f"Objetivo por turno: **{cupo_manual} técnicos**")
            
            for s in semanas:
                st.subheader(f"Análisis de Cobertura - Semana {s}")
                data_s = df_res[df_res['Semana'] == s]
                
                # Crear tabla de cumplimiento
                cob_data = []
                for t in turnos:
                    fila_t = {"Turno": t}
                    for d in dias:
                        conteo = len(data_s[(data_s['Dia'] == d) & (data_s['Turno'] == t)])
                        # Usamos iconos para ver rápido si se cumplió
                        status = "✅" if conteo == cupo_manual else ("⚠️" if conteo > 0 else "❌")
                        fila_t[d] = f"{status} {conteo}"
                    cob_data.append(fila_t)
                
                st.table(pd.DataFrame(cob_data))

    else:
        st.error("No se pudo generar la solución. Revisa el balance entre personal y cupos.")
