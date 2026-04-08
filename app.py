import streamlit as st
import pandas as pd
from pulp import *

st.set_page_config(page_title="Programador Pro 2026 - Equilibrio Total", layout="wide")
st.title("🗓️ Programador de Turnos: Cobertura y Equilibrio de Descansos")

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
    num_semanas = st.radio("Semanas a programar", [4, 5], index=0)
    st.info(f"Personal: {len(df[df[col_car] == cargo_sel])}")

# --- 3. MOTOR ---
if st.button(f"🚀 Generar Programación Equilibrada"):
    df_f = df[df[col_car] == cargo_sel]
    semanas = list(range(1, num_semanas + 1))
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Equilibrio_Carga", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], semanas, dias, turnos), cat='Binary')

    # OBJETIVO PRINCIPAL: Maximizar cobertura de turnos (Llenar los 2, 7 o 3 técnicos)
    prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom] for s in semanas for d in dias for t in turnos])

    # A. RESTRICCIONES DE CUPO (Máximo pedido por turno)
    for s in semanas:
        for d in dias:
            for t in turnos:
                prob += lpSum([asig[e][s][d][t] for e in df_f[col_nom]]) <= cupo_manual

    # B. RESTRICCIONES POR EMPLEADO
    for _, row in df_f.iterrows():
        e = row[col_nom]
        contrato = row[col_des]
        dia_c = "Sabado" if "sabado" in contrato else "Domingo"
        
        # 1. Un turno al día máximo
        for s in semanas:
            for d in dias:
                prob += lpSum([asig[e][s][d][t] for t in turnos]) <= 1

        # 2. CUMPLIMIENTO DE REFORMA (5 días laborables promedio por semana)
        # Total días mes: 4 sem = 20 días labor, 5 sem = 25 días labor.
        prob += lpSum([asig[e][s][d][t] for s in semanas for d in dias for t in turnos]) == num_semanas * 5
        
        # 3. GARANTÍA DE DESCANSO CONTRACTUAL (Exactamente 2 fines de semana libres al mes)
        # Si el mes es de 4 semanas, trabaja 2 y descansa 2.
        # Si el mes es de 5 semanas, trabaja 3 y descansa 2 (o lo que definas, aquí ponemos trabaja 3, descansa 2).
        prob += lpSum([asig[e][s][dia_c][t] for s in semanas for t in turnos]) == (num_semanas - 2)

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
        st.success(f"✅ Programación Equilibrada Generada ({num_semanas} semanas)")

        tab1, tab2, tab3 = st.tabs(["📅 Malla Mensual", "👤 Auditoría Descansos", "🏭 Cobertura Operativa"])

        with tab1:
            for s in semanas:
                st.subheader(f"Semana {s}")
                malla = df_res[df_res['Semana'] == s].pivot(index='Empleado', columns='Dia', values='Turno')
                st.dataframe(malla.reindex(columns=dias), use_container_width=True)

        with tab2:
            met_emp = []
            for e in df_f[col_nom]:
                data_e = df_res[df_res['Empleado'] == e]
                dia_c = "Sabado" if "sabado" in data_e['Contrato'].iloc[0] else "Domingo"
                libres_c = len(data_e[(data_e['Dia'] == dia_c) & (data_e['Turno'] == 'DESCANSO')])
                comp_lv = len(data_e[(data_e['Dia'].isin(["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"])) & (data_e['Turno'] == 'DESCANSO')])
                met_emp.append({"Empleado": e, "Contrato": dia_c, "Libres Finde": f"{libres_c}/2", "Descansos L-V": comp_lv, "Días Totales Laborados": len(data_e[data_e['Turno'] != 'DESCANSO'])})
            st.table(pd.DataFrame(met_emp))

        with tab3:
            for s in semanas:
                st.subheader(f"Cobertura Semana {s}")
                data_s = df_res[df_res['Semana'] == s]
                cob_data = []
                for t in turnos:
                    fila = {"Turno": t}
                    for d in dias:
                        conteo = len(data_s[(data_s['Dia'] == d) & (data_s['Turno'] == t)])
                        fila[d] = f"✅ {conteo}" if conteo == cupo_manual else f"⚠️ {conteo}"
                    cob_data.append(fila)
                st.table(pd.DataFrame(cob_data))
    else:
        st.error("❌ Conflicto Matemático: Tienes más cupos que gente disponible para trabajar 5 días a la semana.")
