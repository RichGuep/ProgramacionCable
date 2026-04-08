import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")
st.title("🗓️ Programador de Turnos: Lógica de Compensatorios y Calendario")

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
    st.header("📅 Periodo")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel_nombre = st.selectbox("Mes", meses_nombres, index=datetime.now().month - 1)
    mes_num = meses_nombres.index(mes_sel_nombre) + 1

    st.divider()
    st.header("⚙️ Operación")
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input(f"Cupo ideal por turno", value=2)

# --- 3. CÁLCULO DE DÍAS ---
num_dias_mes = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = []
dias_esp = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

for d in range(1, num_dias_mes + 1):
    fecha = datetime(ano_sel, mes_num, d)
    dias_mes.append({"n": d, "nombre": dias_esp[fecha.weekday()]})

# --- 4. MOTOR ---
if st.button(f"🚀 Generar Malla {mes_sel_nombre}"):
    df_f = df[df[col_car] == cargo_sel]
    turnos = ["AM", "PM", "Noche"]
    
    # Maximizamos cobertura para que use a los 4 disponibles el finde al máximo
    prob = LpProblem("Malla_Compensada", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias_mes + 1), turnos), cat='Binary')

    # OBJETIVO: Llenar la mayor cantidad de turnos
    prob += lpSum([asig[e][d_info["n"]][t] for e in df_f[col_nom] for d_info in dias_mes for t in turnos])

    # A. RESTRICCIONES DE CUPO
    for d_info in dias_mes:
        d = d_info["n"]
        for t in turnos:
            # Cupo máximo pedido (2 para masters)
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    # B. RESTRICCIONES POR EMPLEADO
    for _, row in df_f.iterrows():
        e = row[col_nom]
        contrato = row[col_des]
        dia_fijo = "Sabado" if "sabado" in contrato else "Domingo"
        
        # 1. Un turno al día
        for d in range(1, num_dias_mes + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1

        # 2. Descanso Biológico (Noche no puede AM/PM mañana)
        for d in range(1, num_dias_mes):
            prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
            prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

        # 3. REGLA CLAVE: Exactamente 2 descansos de fin de semana al mes
        dias_c_mes = [di["n"] for di in dias_mes if di["nombre"] == dia_fijo]
        prob += lpSum([asig[e][d][t] for d in dias_c_mes for t in turnos]) == (len(dias_c_mes) - 2)

        # 4. COMPENSATORIOS: Trabajar 5 días por semana (promedio)
        # Total días a trabajar = (Días del mes / 7) * 5
        total_laboral = int((num_dias_mes / 7) * 5)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias_mes + 1) for t in turnos]) == total_laboral

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] in ['Optimal']:
        st.success(f"✅ Malla generada: 2 {dia_fijo}s libres y compensatorios entre semana aplicados.")
        
        res_list = []
        for d_info in dias_mes:
            d = d_info["n"]
            for e in df_f[col_nom]:
                t_asig = "DESCANSO"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res_list.append({"Dia": d, "Dia_Nom": d_info["nombre"], "Empleado": e, "Turno": t_asig})
        
        df_res = pd.DataFrame(res_list)
        
        # Visualización Semanal
        for s in range((num_dias_mes // 7) + 1):
            i, f = s * 7 + 1, min((s + 1) * 7, num_dias_mes)
            if i <= num_dias_mes:
                st.subheader(f"Semana del {i} al {f}")
                malla = df_res[(df_res['Dia'] >= i) & (df_res['Dia'] <= f)].pivot(index='Empleado', columns='Dia', values='Turno')
                st.dataframe(malla, use_container_width=True)
                
                # Métrica de cobertura
                data_s = df_res[(df_res['Dia'] >= i) & (df_res['Dia'] <= f)]
                cobs = []
                for d_idx in range(i, f + 1):
                    c = len(data_s[(data_s['Dia'] == d_idx) & (data_s['Turno'] != 'DESCANSO')])
                    cobs.append(f"{d_idx}: {c}/{cupo_manual*3}")
                st.caption("Cobertura diaria (Asignados/Cupo Total): " + " | ".join(cobs))
    else:
        st.error("❌ Conflicto de reglas. Intenta revisar el personal disponible.")
