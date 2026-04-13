import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="MovilGo Pro", layout="wide")
TURNOS = ["AM", "PM", "Noche"]

# --- DATA ---
@st.cache_data
def load_data():
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})

df_raw = load_data()

# --- UI ---
meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

mes_sel = st.sidebar.selectbox("Mes", meses)
mes_num = meses.index(mes_sel) + 1
cargo_sel = st.sidebar.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
cupo = st.sidebar.number_input("Cupo por turno", 1, 15, 2)

num_dias = calendar.monthrange(2026, mes_num)[1]

dias_info = [{
    "n": d,
    "nombre": ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()],
    "semana": (d + datetime(2026, mes_num, 1).weekday() - 1)//7 + 1,
    "label": f"{d}-{['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][datetime(2026, mes_num, d).weekday()]}"
} for d in range(1, num_dias+1)]

# --- BOTÓN ---
if st.button("🚀 GENERAR MALLA PRO FINAL"):

    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    empleados = df_f['nombre'].tolist()

    prob = LpProblem("MovilGo_Final", LpMaximize)

    asig = LpVariable.dicts("A", (empleados, range(1, num_dias+1), TURNOS), cat='Binary')
    noches = LpVariable.dicts("N", empleados, lowBound=0)

    # OBJETIVO
    prob += lpSum(asig[e][d][t] for e in empleados for d in range(1, num_dias+1) for t in TURNOS) \
            - 2 * lpSum(noches[e] for e in empleados)

    # COBERTURA
    for d in range(1, num_dias+1):
        for t in TURNOS:
            prob += lpSum(asig[e][d][t] for e in empleados) <= cupo

    # RESTRICCIONES
    for _, row in df_f.iterrows():
        e = row['nombre']
        dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"

        for d in range(1, num_dias+1):
            prob += lpSum(asig[e][d][t] for t in TURNOS) <= 1

            if d < num_dias:
                # descanso real
                prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # evitar muchas noches seguidas
        for d in range(1, num_dias-1):
            prob += asig[e][d]["Noche"] + asig[e][d+1]["Noche"] + asig[e][d+2]["Noche"] <= 2

        dias_ley = [di["n"] for di in dias_info if di["nombre"] == dia_ley]

        # mínimo 2 descansos fin de semana
        prob += lpSum(asig[e][d][t] for d in dias_ley for t in TURNOS) <= (len(dias_ley) - 2)

        # carga mínima
        prob += lpSum(asig[e][d][t] for d in range(1, num_dias+1) for t in TURNOS) >= 18

        # noches KPI
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
            for t in TURNOS:
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

        # DESCANSOS LEY
        idx = g[(g['Turno']=="---") & (g['Nom_Dia']==dia_ley)].head(2).index
        g.loc[idx,"Turno"] = "DESC. LEY"

        # COMPENSATORIOS OBLIGATORIOS
        findes = g[(g['Nom_Dia']==dia_ley) & (g['Turno'].isin(TURNOS))]

        for _, r in findes.iterrows():

            hueco = g[
                (g['Semana']==r['Semana']+1) &
                (g['Turno']=="---") &
                (~g['Nom_Dia'].isin(['Sab','Dom']))
            ].head(1)

            if not hueco.empty:
                g.loc[hueco.index,"Turno"] = "DESC. COMPENSATORIO"
            else:
                # fuerza compensatorio si no hay hueco
                for idx2 in g[
                    (g['Semana']==r['Semana']+1) &
                    (~g['Nom_Dia'].isin(['Sab','Dom']))
                ].index:
                    g.loc[idx2,"Turno"] = "DESC. COMPENSATORIO"
                    break

        # DISPONIBILIDAD INTELIGENTE
        for idx in g[g['Turno']=="---"].index:
            dia = g.loc[idx,"Dia"]
            prev = g[(g['Dia']<dia) & (g['Turno'].isin(TURNOS))].tail(1)

            if not prev.empty:
                g.loc[idx,"Turno"] = f"DISPONIBLE {prev['Turno'].values[0]}"
            else:
                g.loc[idx,"Turno"] = "DISPONIBLE AM"

        final.append(g)

    df_final = pd.concat(final)

    # --- KPIs ---
    kpis = []
    for e, g in df_final.groupby("Empleado"):
        dia_ley = "Sab" if "sab" in str(g['Ley'].iloc[0]).lower() else "Dom"

        kpis.append({
            "Empleado": e,
            "Turnos": len(g[g['Turno'].isin(TURNOS)]),
            "Noches": len(g[g['Turno']=="Noche"]),
            "Compensatorios": len(g[g['Turno']=="DESC. COMPENSATORIO"]),
            "Desc. Ley": len(g[(g['Nom_Dia']==dia_ley) & (g['Turno']=="DESC. LEY")]),
            "Carga %": round(len(g[g['Turno'].isin(TURNOS)]) / num_dias * 100,1)
        })

    df_kpi = pd.DataFrame(kpis)

    # --- UI ---
    st.success("✅ Malla optimizada correctamente")

    tab1, tab2 = st.tabs(["📅 Malla", "📊 KPIs"])

    with tab1:
        st.dataframe(df_final.pivot(index="Empleado", columns="Label", values="Turno"),
                     use_container_width=True)

    with tab2:
        st.dataframe(df_kpi, use_container_width=True)

    # --- EXPORTAR ---
    if st.button("📥 Exportar Excel"):
        with pd.ExcelWriter("malla_final.xlsx") as writer:
            df_final.to_excel(writer, sheet_name="Malla")
            df_kpi.to_excel(writer, sheet_name="KPIs")

        with open("malla_final.xlsx","rb") as f:
            st.download_button("Descargar archivo", f, "malla_final.xlsx")
