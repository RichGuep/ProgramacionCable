import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Cupo Blindado", layout="wide", page_icon="⚡")

# --- 2. MOTOR DE CARGA ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df.rename(columns={'nombre': 'nombre', 'cargo': 'cargo', 'descanso': 'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_objetivo = st.number_input("Cupo Obligatorio por Turno", 1, 10, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button("🚀 GENERAR MALLA (CUPO OBLIGATORIO)"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Blindando cupos AM, PM y Noche...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Cupo_Total", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], range(len(semanas)), ["AM", "PM", "Noche"]), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (df_f['nombre'], range(1, num_dias + 1)), cat='Binary')
        
        # Objetivo: Maximizar cobertura pero con penalización por no llenar turnos
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                # REGLA DE ORO: La suma de asignados DEBE ser al menos el cupo_objetivo
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) >= cupo_objetivo

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # Descansos de ley (2 o 3 según el mes)
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
            min_desc = 3 if len(semanas) >= 5 else 2
            prob += lpSum([es_descanso[e][d] for d in dias_fds]) == min_desc

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) + es_descanso[e][d] == 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            for s_idx, dias_s in enumerate(semanas):
                prob += lpSum([t_sem[e][s_idx][t] for t in ["AM", "PM", "Noche"]]) <= 1
                for d in dias_s:
                    for t in ["AM", "PM", "Noche"]:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"; s_act = next(i for i, sem in enumerate(semanas) if d in sem)
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[e][d][t]) == 1: t_real = t
                    t_base = "AM"
                    for t in ["AM", "PM", "Noche"]:
                        if value(t_sem[e][s_act][t]) == 1: t_base = t
                    res_list.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            df_res['Final'] = ""
            # ASIGNACIÓN PRIORITARIA: Llenar AM, luego PM, luego Noche
            for d in range(1, num_dias + 1):
                for t in ["AM", "PM", "Noche"]:
                    # Buscamos quiénes están asignados a este turno este día
                    mask = (df_res['Dia'] == d) & (df_res['Turno'] == t)
                    indices = df_res[mask].index
                    for i, idx in enumerate(indices):
                        if i < cupo_objetivo:
                            df_res.at[idx, 'Final'] = f"TITULAR {t}"
                        else:
                            df_res.at[idx, 'Final'] = f"DISPONIBLE {t}"
            
            for idx in df_res[df_res['Turno'] == "---"].index:
                dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."
            
            st.session_state['df_final'] = df_res
            status.empty(); prog_bar.empty()
        else:
            st.error("🚨 IMPOSIBLE: No hay suficiente gente para cubrir 2 AM, 2 PM y 2 Noche simultáneamente cumpliendo descansos.")

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Final')
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        
        def style_v(v):
            if 'TITULAR' in v: return 'background-color: #cce5ff; color: #004085; font-weight: bold'
            if 'DISPONIBLE' in v: return 'background-color: #d4edda; color: #155724'
            if 'LEY' in v: return 'background-color: #ff9900; color: white'
            if 'COMP' in v: return 'background-color: #ffd966'
            return ''

        st.dataframe(m_f[cols].style.map(style_v), use_container_width=True)
