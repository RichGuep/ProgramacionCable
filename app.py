import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Versión Excel", layout="wide", page_icon="📅")

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
        cupo_minimo = st.number_input("Cupo Mínimo Titular", 1, 20, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [ [d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num) ]

    if st.button("🚀 GENERAR MALLA (LÓGICA RICHARD)"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Calculando relevos y bloques de descanso...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Final_Richard", LpMaximize)
        
        # Variables
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], range(len(semanas)), ["AM", "PM", "Noche"]), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (df_f['nombre'], range(1, num_dias + 1)), cat='Binary')

        # OBJETIVO: Maximizar días trabajados (para forzar que el resto sean descansos exactos)
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # --- 4 DESCANSOS EXACTOS AL MES ---
            prob += lpSum([es_descanso[e][d] for d in range(1, num_dias + 1)]) == 4
            
            # --- 2 DESCANSOS EN EL FIN DE SEMANA DE LEY ---
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
            prob += lpSum([es_descanso[e][d] for d in dias_fds]) == 2

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) + es_descanso[e][d] == 1
                
                # Prohibir descanso día por medio (Bloques de trabajo)
                if d < num_dias:
                    prob += es_descanso[e][d] + es_descanso[e][d+1] <= 1
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Turno fijo por semana
            for s_idx, dias_s in enumerate(semanas):
                prob += lpSum([t_sem[e][s_idx][t] for t in ["AM", "PM", "Noche"]]) <= 1
                for d in dias_s:
                    for t in ["AM", "PM", "Noche"]:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

        # CUPO MÍNIMO (Asegurar que siempre haya personal titular)
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) >= cupo_minimo

        status.text("80% - Finalizando optimización...")
        prog_bar.progress(80)
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
            
            # --- LÓGICA DE ASIGNACIÓN: TITULAR VS DISPONIBLE ---
            df_res['Final'] = ""
            # Primero asignamos titulares según el cupo
            for (d, t), group in df_res[df_res['Turno'] != "---"].groupby(['Dia', 'Turno']):
                for i, idx in enumerate(group.index):
                    df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_minimo else f"DISPONIBLE {t}"
            
            # Marcamos los descansos
            for idx in df_res[df_res['Turno'] == "---"].index:
                dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty(); prog_bar.empty()
        else:
            st.error("🚨 Imposible cumplir el cupo con 4 descansos. Revisa el personal.")

    # --- RENDERIZADO ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        
        def style_v(v):
            if 'TITULAR' in v: return 'background-color: #cce5ff; color: #004085'
            if 'DISPONIBLE' in v: return 'background-color: #d4edda; color: #155724; font-style: italic'
            if 'DESC' in v: return 'background-color: #ff9900; color: white; font-weight: bold'
            return ''

        st.dataframe(m_f[cols].style.map(style_v), use_container_width=True)
        
        # Auditoría de los 4 días
        st.write("### ⚖️ Auditoría de Descansos (Deberían ser 4)")
        audit = df_v[df_v['Final'].str.contains('DESC')].groupby('Empleado').size()
        st.table(audit)
