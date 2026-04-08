import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro CableMovil", layout="wide")
st.title("🗓️ Programación Cablemovil")

# --- 1. CARGA ---
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
    st.error(f"Error: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("📅 Configuración")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)

# --- 3. MOTOR ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = [{"n": d, "nombre": ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"][datetime(ano_sel, mes_num, d).weekday()]} for d in range(1, num_dias + 1)]

if st.button(f"🚀 Generar Malla con DISPO"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Prioridad_DISPO", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e, contrato = row[col_nom], row[col_des]
        dia_c = "Sabado" if "sabado" in contrato else "Domingo"
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) == int((num_dias / 7) * 5)
        d_c_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c]
        prob += lpSum([asig[e][d][t] for d in d_c_m for t in turnos]) == (len(d_c_m) - 2)

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        res = []
        for d_i in dias_mes:
            d = d_i["n"]
            for e in df_f[col_nom]:
                t_asig = "---"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res.append({
                    "Dia": d, 
                    "Nombre": d_i["nombre"], 
                    "Empleado": e, 
                    "Turno": t_asig, 
                    "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]
                })
        
        df_res = pd.DataFrame(res)
        
        # --- NUEVO PROCESAMIENTO (MÁS SEGURO) ---
        lista_final = []
        for emp_name, grupo in df_res.groupby("Empleado"):
            grupo = grupo.copy()
            sin_turno = grupo[grupo['Turno'] == '---']
            contrato = grupo['Contrato'].iloc[0]
            dia_c = "Sabado" if "sabado" in contrato else "Domingo"
            
            # 2 Descansos contractuales
            libres_f_indices = sin_turno[sin_turno['Nombre'] == dia_c].head(2).index
            grupo.loc[libres_f_indices, 'Turno'] = 'DESCANSO'
            
            # El resto de libres hasta completar 8 (para mes de 4 sem) o proporcional
            max_libres = num_dias - int((num_dias / 7) * 5)
            
            indices_restantes = grupo[grupo['Turno'] == '---'].index
            for idx in indices_restantes:
                if len(grupo[grupo['Turno'] == 'DESCANSO']) < max_libres:
                    grupo.loc[idx, 'Turno'] = 'DESCANSO'
                else:
                    grupo.loc[idx, 'Turno'] = 'DISPO'
            
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)

        # --- VISUALIZACIÓN ---
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"
        malla_pivot = df_final.pivot(index='ID', columns='Dia', values='Turno')
        st.dataframe(malla_pivot.reindex(columns=range(1, num_dias + 1)), use_container_width=True)
        
        # Auditoría simple
        st.divider()
        st.subheader("🏭 Cobertura Lograda")
        for t in turnos:
            c_t = len(df_final[df_final['Turno'] == t])
            st.write(f"Turno {t}: {c_t} asignaciones en el mes.")
    else:
        st.error("No hay solución.")
