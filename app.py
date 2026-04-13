import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- CONFIG ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- LOGIN ---
def login():
    if 'auth' not in st.session_state:
        st.session_state['auth'] = True
login()

# --- DATA ---
@st.cache_data
def load_data():
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})

df_raw = load_data()

# --- SIDEBAR ---
meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

mes_sel = st.sidebar.selectbox("Mes", meses)
mes_num = meses.index(mes_sel) + 1
cargo_sel = st.sidebar.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
cupo = st.sidebar.number_input("Cupo por turno", 1, 15, 2)

# --- CALENDARIO ---
num_dias = calendar.monthrange(2026, mes_num)[1]

dias_info = [{
    "n": d,
    "nombre": ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()],
    "semana": (d + datetime(2026, mes_num, 1).weekday() - 1)//7 + 1,
    "label": f"{d}-{['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][datetime(2026, mes_num, d).weekday()]}"
} for d in range(1, num_dias+1)]

# --- BOTON ---
if st.button("🚀 GENERAR MALLA PRO"):

    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    empleados = df_f['nombre'].tolist()

    prob = LpProblem("MovilGo", LpMaximize)

    asig = LpVariable.dicts("A", (empleados, range(1, num_dias+1), LISTA_TURNOS), cat='Binary')
    noches = LpVariable.dicts("N", empleados, lowBound=0)

    # OBJETIVO
    prob += lpSum(asig[e][d][t] for e in empleados for d in range(1, num_dias+1) for t in LISTA_TURNOS) \
            - 2*lpSum(noches[e] for e in empleados)

    # COBERTURA
    for di in dias_info:
        for t in LISTA_TURNOS:
            prob += lpSum(asig[e][di["n"]][t] for e in empleados) <= cupo

    # RESTRICCIONES
    for _, row in df_f.iterrows():
        e = row['nombre']
        dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"

        for d in range(1, num_dias+1):
            prob += lpSum(asig[e][d][t] for t in LISTA_TURNOS) <= 1

            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_ley]

        # mínimo 2 descansos fin de semana
        prob += lpSum(asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS) <= (len(dias_criticos) - 2)

        # carga mínima
        prob += lpSum(asig[e][d][t] for d in range(1, num_dias+1) for t in LISTA_TURNOS) >= 18

        # noches
        prob += noches[e] == lpSum(asig[e][d]["Noche"] for d in range(1, num_dias+1))

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] != 'Optimal':
        st.error("❌ No hay solución")
        st.stop()

    # --- RESULTADO BASE ---
    res = []
    for di in dias_info:
        for e in empleados:
            turno = "---"
            for t in LISTA_TURNOS:
                if value(asig[e][di["n"]][t]) == 1:
                    turno = t

            res.append({
                "Dia": di["n"],
                "Label": di["label"],
                "Semana": di["semana"],
                "Nom_Dia": di["nombre"],
                "Empleado": e,
                "Turno": turno,
                "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]
            })

    df_res = pd.DataFrame(res)

    # --- POST PROCESO ---
    final = []

    for emp, g in df_res.groupby("Empleado"):
        g = g.sort_values("Dia").copy()
        dia_ley = "Sab" if "sab" in str(g['Ley'].iloc[0]).lower() else "Dom"

        # descansos ley
        idx = g[(g['Turno']=="---") & (g['Nom_Dia']==dia_ley)].head(2).index
        g.loc[idx,"Turno"] = "DESC. LEY"

        # compensatorios (máx 1 por semana)
        usadas = set()
        findes = g[(g['Nom_Dia']==dia_ley) & (g['Turno'].isin(LISTA_TURNOS))]

        for _, r in findes.iterrows():
            if r['Semana'] in usadas:
                continue

            hueco = g[(g['Semana']==r['Semana']+1) &
                      (g['Turno']=="---") &
                      (~g['Nom_Dia'].isin(['Sab','Dom']))].head(1)

            if not hueco.empty:
                g.loc[hueco.index,"Turno"] = "DESC. COMPENSATORIO"
                usadas.add(r['Semana'])

        # disponibilidad inteligente
        for idx in g[g['Turno']=="---"].index:
            dia = g.loc[idx,"Dia"]
            prev = g[(g['Dia']<dia) & (g['Turno'].isin(LISTA_TURNOS))].tail(1)

            if not prev.empty:
                g.loc[idx,"Turno"] = f"DISPONIBLE {prev['Turno'].values[0]}"
            else:
                g.loc[idx,"Turno"] = "DISPONIBLE AM"

        final.append(g)

    df_final = pd.concat(final)

    # --- KPIs ---
    kpis = []
    for e, g in df_final.groupby("Empleado"):
        kpis.append({
            "Empleado": e,
            "Turnos": len(g[g['Turno'].isin(LISTA_TURNOS)]),
            "Noches": len(g[g['Turno']=="Noche"]),
            "Compensatorios": len(g[g['Turno']=="DESC. COMPENSATORIO"]),
            "Carga %": round(len(g[g['Turno'].isin(LISTA_TURNOS)]) / num_dias * 100,1)
        })

    df_kpi = pd.DataFrame(kpis)

    # --- UI ---
    st.success("✅ Malla generada")

    tab1, tab2 = st.tabs(["📅 Malla", "📊 KPIs"])

    with tab1:
        st.dataframe(df_final.pivot(index="Empleado", columns="Label", values="Turno"),
                     use_container_width=True)

    with tab2:
        st.dataframe(df_kpi, use_container_width=True)

    # --- EXPORTAR ---
    if st.button("📥 Exportar Excel"):
        with pd.ExcelWriter("malla.xlsx") as writer:
            df_final.to_excel(writer, sheet_name="Malla")
            df_kpi.to_excel(writer, sheet_name="KPIs")

        with open("malla.xlsx","rb") as f:
            st.download_button("Descargar", f, "malla.xlsx")
