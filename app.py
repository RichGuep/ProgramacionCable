import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="MovilGo PRO", layout="wide")

# --- LOGIN ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = True

# --- DATA ---
@st.cache_data
def load_data():
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    return df

df_raw = load_data()

# --- CONFIG ---
meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

mes_sel = st.selectbox("Mes", meses)
mes_num = meses.index(mes_sel) + 1

cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))

cupos_por_cargo = {
    "Master": 2,
    "Tecnico A": 7,
    "Tecnico B": 3
}

cupo = cupos_por_cargo.get(cargo_sel, 2)

# --- CALENDARIO ---
num_dias = calendar.monthrange(2026, mes_num)[1]
dias = list(range(1, num_dias + 1))
turnos = ["AM", "PM", "Noche"]

cal = calendar.Calendar()
semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

# --- BOTON ---
if st.button("🚀 GENERAR MALLA PRO"):

    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    empleados = df_f['nombre'].tolist()

    # --- GRUPOS ---
    grupo_A = empleados[::2]
    grupo_B = empleados[1::2]

    prob = LpProblem("Turnos_PRO", LpMaximize)

    # --- VARIABLES ---
    asig = LpVariable.dicts("A", (empleados, dias, turnos), 0, 1, LpBinary)
    descanso = LpVariable.dicts("D", (empleados, dias), 0, 1, LpBinary)
    faltante = LpVariable.dicts("F", (dias, turnos), 0, None, LpInteger)

    # --- OBJETIVO (CLAVE) ---
    prob += (
        lpSum(asig[e][d][t] for e in empleados for d in dias for t in turnos)
        - 1000 * lpSum(faltante[d][t] for d in dias for t in turnos)
    )

    # --- RESTRICCIONES BASE ---
    for e in empleados:
        for d in dias:
            prob += lpSum(asig[e][d][t] for t in turnos) + descanso[e][d] == 1

            if d < num_dias:
                prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in turnos) <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

    # --- FINES DE SEMANA ---
    for i, semana in enumerate(semanas):
        fds = [d for d in semana if datetime(2026, mes_num, d).weekday() >= 5]

        grupo_desc = grupo_A if i % 2 == 0 else grupo_B

        for e in empleados:
            for d in fds:
                if e in grupo_desc:
                    prob += descanso[e][d] == 1
                else:
                    prob += descanso[e][d] == 0

    # --- COBERTURA CON FALTANTE (CLAVE PRO) ---
    for d in dias:
        for t in turnos:
            prob += (
                lpSum(asig[e][d][t] for e in empleados)
                + faltante[d][t]
                == cupo
            )

    # --- ROTACIÓN SUAVE (PRO) ---
    for e in empleados:
        prob += lpSum(asig[e][d]["Noche"] for d in dias) <= len(dias) * 0.4

    # --- SOLVER ---
    prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))

    # --- RESULTADOS ---
    res = []

    for d in dias:
        dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]

        for e in empleados:
            turno = "---"
            for t in turnos:
                if value(asig[e][d][t]) == 1:
                    turno = t

            res.append({
                "Dia": d,
                "Label": f"{d}-{dn}",
                "Empleado": e,
                "Turno": turno
            })

    df_res = pd.DataFrame(res)

    df_res["Final"] = df_res["Turno"].apply(lambda x: "DESCANSO" if x == "---" else x)

    st.subheader("📅 Malla")
    m = df_res.pivot(index="Empleado", columns="Label", values="Final")
    st.dataframe(m, use_container_width=True)

    # --- ALERTA FALTANTES ---
    faltantes_totales = sum(value(faltante[d][t]) for d in dias for t in turnos)

    if faltantes_totales > 0:
        st.warning(f"⚠️ Faltantes detectados: {int(faltantes_totales)} turnos no cubiertos")
    else:
        st.success("✅ Cobertura completa")
