import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Auditoría de Turnos 2026", layout="wide")

st.title("📊 Dashboard de Programación y Auditoría Operativa")

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
    st.error(f"Error al leer Excel: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("📅 Calendario")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    
    st.divider()
    cargo_sel = st.selectbox("Cargo a Evaluar", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo objetivo por turno", value=2)

# --- 3. LÓGICA DE DÍAS ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = []
dias_esp = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    dias_mes.append({"n": d, "nombre": dias_esp[fecha.weekday()]})

# --- 4. MOTOR ---
if st.button(f"🔍 Generar y Analizar {mes_sel}"):
    df_f = df[df[col_car] == cargo_sel]
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Auditoria_Turnos", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    # Objetivo: Maximizar cobertura
    prob += lpSum([asig[e][d_info["n"]][t] for e in df_f[col_nom] for d_info in dias_mes for t in turnos])

    for d_info in dias_mes:
        d = d_info["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e, contrato = row[col_nom], row[col_des]
        dia_c = "Sabado" if "sabado" in contrato else "Domingo"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
        for d in range(1, num_dias): # Descanso Biológico
            prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
            prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

        dias_c_mes = [di["n"] for di in dias_mes if di["nombre"] == dia_c]
        prob += lpSum([asig[e][d][t] for d in dias_c_mes for t in turnos]) == (len(dias_c_mes) - 2)
        
        dias_laborar = int((num_dias / 7) * 5)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) == dias_laborar

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        res = []
        for d_info in dias_mes:
            d = d_info["n"]
            for e in df_f[col_nom]:
                t_asig = "DESCANSO"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res.append({
                    "Dia": d, "Nombre": d_info["nombre"], "Empleado": e, 
                    "Turno": t_asig, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]
                })
        df_res = pd.DataFrame(res)

        # --- VISUALIZACIÓN ---
        tab1, tab2, tab3 = st.tabs(["📅 Malla Mensual", "🚨 Diagnóstico de Faltantes", "👤 Auditoría Individual"])

        with tab1:
            st.subheader(f"Malla de Turnos - {mes_sel} (Tipo Contrato visible)")
            df_res['Emp_Contrato'] = df_res['Empleado'] + " (" + df_res['Contrato'].str.upper() + ")"
            malla = df_res.pivot(index='Emp_Contrato', columns='Dia', values='Turno')
            st.dataframe(malla, use_container_width=True)

        with tab2:
            st.subheader("🚩 ¿Dónde nos falta gente?")
            st.write("Esta tabla muestra los turnos que quedaron por debajo del cupo ideal.")
            faltantes = []
            for d_info in dias_mes:
                for t in turnos:
                    cont = len(df_res[(df_res['Dia']==d_info['n']) & (df_res['Turno']==t)])
                    if cont < cupo_manual:
                        faltantes.append({"Día": d_info['n'], "Nombre": d_info['nombre'], "Turno": t, "Contados": cont, "Faltan": cupo_manual - cont})
            
            if faltantes:
                st.warning(f"Se detectaron turnos con cobertura incompleta debido a descansos contractuales.")
                st.table(pd.DataFrame(faltantes))
            else:
                st.success("✅ ¡Cobertura 100% en todos los turnos!")

        with tab3:
            st.subheader("📋 Resumen de Rotación y Descansos")
            met_ind = []
            for e in df_f[col_nom]:
                d_e = df_res[df_res['Empleado'] == e]
                tipo = d_e['Contrato'].iloc[0]
                dia_c = "Sabado" if "sabado" in tipo else "Domingo"
                
                libres_c = len(d_e[(d_e['Nombre']==dia_c) & (d_e['Turno']=='DESCANSO')])
                compens_lv = len(d_e[(~d_e['Nombre'].isin(["Sabado", "Domingo"])) & (d_e['Turno']=='DESCANSO')])
                turnos_dist = d_e[d_e['Turno']!='DESCANSO']['Turno'].unique()
                
                met_ind.append({
                    "Empleado": e, "Contrato": tipo.upper(), "Libres Finde": f"{libres_c} de {len(d_e[d_e['Nombre']==dia_c])}",
                    "Compensatorios L-V": compens_lv, "Turnos en el mes": ", ".join(turnos_dist)
                })
            st.table(pd.DataFrame(met_ind))
    else:
        st.error("❌ El modelo no pudo encontrar una solución con el personal actual.")
