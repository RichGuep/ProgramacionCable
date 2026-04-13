import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="MovilGo PRO", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    return df

df_raw = load_data()

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

num_dias = calendar.monthrange(2026, mes_num)[1]
dias = list(range(1, num_dias + 1))
turnos = ["AM", "PM", "Noche"]

cal = calendar.Calendar()
semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

if st.button("🚀 GENERAR MALLA FINAL"):

    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    empleados = df_f['nombre'].tolist()

    prob = LpProblem("Turnos_REAL", LpMaximize)

    asig = LpVariable.dicts("A", (empleados, dias, turnos), 0, 1, LpBinary)
    descanso = LpVariable.dicts("D", (empleados, dias), 0, 1, LpBinary)

    # OBJETIVO: maximizar asignaciones (menos descanso)
    prob += lpSum(asig[e][d][t] for e in empleados for d in dias for t in turnos)

    # --- REGLAS BASE ---
    for e in empleados:
        for d in dias:
            prob += lpSum(asig[e][d][t] for t in turnos) + descanso[e][d] == 1

            if d < num_dias:
                prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in turnos) <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

    # --- FINES DE SEMANA (MINIMO 2) ---
    for _, row in df_f.iterrows():
        e = row['nombre']

        dia_ley = "Sab" if "sab" in str(row['descanso']).lower() else "Dom"

        dias_ley = [
            d for d in dias
            if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley
        ]

        prob += lpSum(descanso[e][d] for d in dias_ley) >= 2

    # --- COMPENSATORIOS (1 SOLO SI TRABAJA FDS) ---
    for _, row in df_f.iterrows():
        e = row['nombre']

        dia_ley = "Sab" if "sab" in str(row['descanso']).lower() else "Dom"

        for i, semana in enumerate(semanas[:-1]):

            dias_fds = [
                d for d in semana
                if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley
            ]

            dias_sem_sig = [
                d for d in semanas[i+1]
                if datetime(2026, mes_num, d).weekday() < 5
            ]

            if dias_fds and dias_sem_sig:
                trabajo = lpSum(asig[e][d][t] for d in dias_fds for t in turnos)

                prob += lpSum(descanso[e][d] for d in dias_sem_sig) <= trabajo

    # --- COBERTURA ---
    for d in dias:
        for t in turnos:
            prob += lpSum(asig[e][d][t] for e in empleados) >= cupo

    # --- SOLVER ---
    prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))

    res = []

    for d in dias:
        dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]

        for e in empleados:
            turno = None
            for t in turnos:
                if value(asig[e][d][t]) == 1:
                    turno = t

            if turno:
                estado = f"TITULAR {turno}"
            else:
                estado = "DESCANSO"

            res.append({
                "Empleado": e,
                "Dia": f"{d}-{dn}",
                "Estado": estado
            })

    df_res = pd.DataFrame(res)

    # --- DISPONIBLES (CLAVE FINAL) ---
    for d in dias:
        for t in turnos:
            idxs = df_res[
                (df_res["Dia"].str.startswith(str(d))) &
                (df_res["Estado"].str.contains(t))
            ].index

            for i, idx in enumerate(idxs):
                if i >= cupo:
                    df_res.at[idx, "Estado"] = f"DISPONIBLE {t}"

    st.dataframe(df_res.pivot(index="Empleado", columns="Dia", values="Estado"),
                 use_container_width=True)
