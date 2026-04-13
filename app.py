import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Flexibilidad Total", layout="wide", page_icon="🧩")

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
        cupo_solicitado = st.number_input("Cupo por Turno", 1, 20, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [ [d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num) ]

    if st.button("🚀 GENERAR MALLA FLEXIBLE"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Buscando la mejor ubicación para los compensatorios...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Flexible", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        
        # Objetivo: Maximizar cobertura y estabilidad
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley_cont = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # --- REGLA 1: CUOTA DE DESCANSOS (4 al mes) ---
            # Esto garantiza que todos descansen, pero no dice CUÁNDO (excepto los de ley)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]]) == (num_dias - 4)

            # --- REGLA 2: DESCANSOS DE LEY (2 de fin de semana) ---
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley_cont]
            prob += lpSum([asig[e][d][t] for d in dias_fds for t in ["AM", "PM", "Noche"]]) == (len(dias_fds) - 2)

            # --- REGLA 3: SEGURIDAD (Transiciones) ---
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # --- REGLA 4: CUPO BLINDADO (La prioridad de la operación) ---
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) == cupo_solicitado

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[e][d][t]) == 1: t_real = t
                    res_list.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            
            # --- POST-PROCESADO: ETIQUETADO INTELIGENTE ---
            for emp, grupo in df_res.groupby("Empleado"):
                dia_ley_nom = "Sab" if "sab" in str(grupo.iloc[0]['Ley']).lower() else "Dom"
                for idx in grupo.index:
                    if df_res.at[idx, 'Turno'] == "---":
                        if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom:
                            df_res.at[idx, 'Final'] = "DESCANSO LEY"
                        else:
                            df_res.at[idx, 'Final'] = "COMPENSATORIO"
                    else:
                        df_res.at[idx, 'Final'] = df_res.at[idx, 'Turno']
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()
        else:
            st.error("🚨 Imposible cumplir el cupo y dar 4 descansos. Revisa si tienes suficiente personal.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        t1, t2 = st.tabs(["📅 Malla Principal", "⚖️ Auditoría de Descansos"])
        
        with t1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            st.dataframe(m_f[cols].style.map(lambda v: 'background-color: #ff9900; color: white;' if 'DESCANSO' in v or 'COMP' in v else ''), use_container_width=True)
            
        with t2:
            audit = df_v[df_v['Final'].str.contains('DESCANSO') | df_v['Final'].str.contains('COMP')].groupby(['Empleado', 'Final']).size().unstack(fill_value=0)
            st.write("### Resumen de Descansos por Persona")
            st.table(audit)
