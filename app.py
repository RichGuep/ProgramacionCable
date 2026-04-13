import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Freeway 8 Masters", layout="wide")

# --- CARGA ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_req = 2 # Blindado a 2 como pediste

    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button("🚀 GENERAR PROGRAMACIÓN"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        prob = LpProblem("Freeway_8_Masters", LpMaximize)

        # Variables
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (empleados, dias_rango), cat='Binary')

        # Objetivo: Maximizar días trabajados (para usar disponibilidades)
        prob += lpSum(asig[e][d][t] for e in empleados for d in dias_rango for t in TURNOS)

        # 1. COBERTURA TOTAL (Mínimo 2 por turno)
        for d in dias_rango:
            for t in TURNOS:
                prob += lpSum(asig[e][d][t] for e in empleados) >= cupo_req

        # 2. REGLAS LABORALES RICHARD
        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # Forzar exactamente 4 descansos al mes (2 Ley + 2 Comp)
            prob += lpSum(es_descanso[e][d] for d in dias_rango) == 4

            for d in dias_rango:
                prob += lpSum(asig[e][d][t] for t in TURNOS) + es_descanso[e][d] == 1
                if d < num_dias:
                    prob += es_descanso[e][d] + es_descanso[e][d+1] <= 1 # No descansos seguidos
                    prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Lógica de compensatorios por semana
            for s_idx, dias_s in enumerate(semanas):
                dia_cont = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
                if dia_cont and s_idx + 1 < len(semanas):
                    d_c = dia_cont[0]
                    dias_lv_sig = [dia for dia in semanas[s_idx+1] if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, dia).weekday()] not in ["Sab", "Dom"]]
                    # Si trabaja el FDS de ley, descansa un día L-V de la siguiente
                    prob += lpSum(es_descanso[e][dia] for dia in dias_lv_sig) >= lpSum(asig[e][d_c][t] for t in TURNOS)

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    t_asig = "---"
                    for t in TURNOS:
                        if value(asig[e][d][t]) == 1: t_asig = t
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})

            df_res = pd.DataFrame(res)
            df_res['Final'] = ""
            
            # Clasificación Titular vs Disponible
            for d in dias_rango:
                for t in TURNOS:
                    idxs = df_res[(df_res['Dia'] == d) & (df_res['Turno'] == t)].index
                    for i, idx in enumerate(idxs):
                        if i < cupo_req:
                            df_res.at[idx, 'Final'] = f"TITULAR {t}"
                        else:
                            df_res.at[idx, 'Final'] = f"DISPONIBLE {t}"
            
            # Etiquetas de descanso
            for idx in df_res[df_res['Turno'] == "---"].index:
                dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."

            st.success("✅ Malla generada: 2 Titulares por turno + Disponibles")
            m_f = df_res.pivot(index="Empleado", columns="Label", values="Final")
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            
            def style_f(v):
                if 'TITULAR' in v: return 'background-color: #003366; color: white; font-weight: bold'
                if 'DISPONIBLE' in v: return 'background-color: #d4edda; color: #155724'
                if 'LEY' in v: return 'background-color: #ff9900; color: white'
                if 'COMP' in v: return 'background-color: #ffd966'
                return ''
            
            st.dataframe(m_f[cols].style.applymap(style_f), use_container_width=True)
        else:
            st.error("❌ Conflicto matemático. Verifica que los 8 empleados tengan días de descanso de ley (Sab/Dom) balanceados.")
