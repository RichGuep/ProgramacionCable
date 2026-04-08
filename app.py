import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programador de Turnos con Auditoría de Métricas")

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
if st.button(f"🚀 Generar y Auditar {cargo_sel}"):
    df_f = df[df[col_car] == cargo_sel]
    semanas, dias, turnos = [1, 2, 3, 4], ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"], ["AM", "PM", "Noche"]
    
    prob = LpProblem("Malla_Auditada", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], semanas, dias, turnos), cat='Binary')

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
            prob += lpSum([asig[e][s][d][t] for d in dias for t in turnos]) == 5 # 5 días laborables
        
        dia_c = "Sabado" if "sabado" in row[col_des] else "Domingo"
        prob += lpSum([asig[e][s][dia_c][t] for s in semanas for t in turnos]) <= 2 # Min 2 libres al mes

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesar resultados
        res_list = []
        for s in semanas:
            for d in dias:
                for e in df_f[col_nom]:
                    t_asig = "DESCANSO"
                    for t in turnos:
                        if value(asig[e][s][d][t]) == 1: t_asig = t
                    res_list.append({"Semana": s, "Dia": d, "Empleado": e, "Turno": t_asig, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]})
        
        df_res = pd.DataFrame(res_list)
        
        # --- VISUALIZACIÓN ---
        st.success("✅ Malla Mensual Generada")
        tabs = st.tabs([f"Semana {s}" for s in semanas])
        for i, s in enumerate(semanas):
            with tabs[i]:
                malla = df_res[df_res['Semana'] == s].pivot(index='Empleado', columns='Dia', values='Turno')
                st.dataframe(malla.reindex(columns=dias), use_container_width=True)

        # --- PANEL DE MÉTRICAS Y AUDITORÍA ---
        st.divider()
        st.header("📊 Auditoría de Cumplimiento Mensual")
        
        metricas = []
        for e in df_f[col_nom]:
            data_emp = df_res[df_res['Empleado'] == e]
            contrato = data_emp['Contrato'].iloc[0]
            dia_c = "Sabado" if "sabado" in contrato else "Domingo"
            
            # Conteo de Sábados/Domingos Libres
            libres_contrato = len(data_emp[(data_emp['Dia'] == dia_c) & (data_emp['Turno'] == 'DESCANSO')])
            
            # Conteo de Compensatorios (Descansos entre Lunes y Viernes)
            dias_semana = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]
            compensatorios = len(data_emp[(data_emp['Dia'].isin(dias_semana)) & (data_emp['Turno'] == 'DESCANSO')])
            
            # Rotación de turnos (Cuantos turnos diferentes tuvo)
            turnos_unicos = data_emp[data_emp['Turno'] != 'DESCANSO']['Turno'].nunique()
            
            metricas.append({
                "Empleado": e,
                "Día Contrato": dia_c,
                "Fines de Semana Libres": f"{libres_contrato} / 4",
                "Compensatorios (L-V)": compensatorios,
                "Estabilidad Turno": "Alta" if turnos_unicos == 1 else ("Media" if turnos_unicos == 2 else "Baja")
            })
        
        st.table(pd.DataFrame(metricas))
        
        # Alerta de Cumplimiento Legal
        if all(int(m["Fines de Semana Libres"].split()[0]) >= 2 for m in metricas):
            st.info("⚖️ **Estatus Legal:** Se cumple con el mínimo de 2 descansos dominicales/sabatinos al mes para todo el personal.")
        else:
            st.warning("⚠️ **Atención:** Algunos empleados tienen menos de 2 descansos en su día contractual.")

    else:
        st.error("No se pudo generar la malla. Revisa la disponibilidad de personal.")
