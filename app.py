import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Seguridad Total", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. MOTOR DE OPTIMIZACIÓN ---
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
        st.header("⚙️ Parámetros")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    semanas = {}
    for d in range(1, num_dias + 1):
        s = datetime(2026, mes_num, d).isocalendar()[1]
        if s not in semanas: semanas[s] = []
        semanas[s].append(d)

    if st.button("🚀 GENERAR MALLA SEGURA"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Aplicando Candados de Seguridad Circadiana...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Security", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], semanas.keys(), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # OBJETIVO: Cobertura total + Estabilidad Semanal
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 1000000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([t_sem[e][s][t] * 100 for e in df_f['nombre'] for s in semanas.keys() for t in LISTA_TURNOS])

        for d in range(1, num_dias + 1):
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) + hueco[d][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                
                # --- MATRIZ DE SEGURIDAD (CANDADOS) ---
                if d < num_dias:
                    # 1. DE NOCHE -> NADA (Descanso obligatorio)
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    
                    # 2. DE PM -> PROHIBIDO AM (Descanso insuficiente)
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                    
                    # 3. DE PM -> Solo permite PM o Noche (ya cubierto por exclusión de AM)

            # Estabilidad Semanal
            for s_idx, dias_s in semanas.items():
                prob += lpSum([t_sem[e][s_idx][t] for t in LISTA_TURNOS]) <= 1
                for d in dias_s:
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

            # Ley 2+2
            dias_criticos = [di for di in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, di).weekday()] == dia_l]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) == (len(dias_criticos) - 2)

        prog_bar.progress(60)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"; s_act = datetime(2026, mes_num, d).isocalendar()[1]
                    for t in LISTA_TURNOS:
                        if value(asig[e][d][t]) == 1: t_real = t
                    t_base = "AM"
                    for t in LISTA_TURNOS:
                        if value(t_sem[e][s_act][t]) == 1: t_base = t
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: df_res.at[i, 'Final'] = "DESC. LEY"
                elif i > 0 and "Noche" in str(df_res.at[i-1, 'Turno']): df_res.at[i, 'Final'] = "COMPENSATORIO (POST-NOCHE)"
                else: df_res.at[i, 'Final'] = f"DISPONIBLE {r['Base']}"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()
        else:
            st.error("Conflicto de reglas. Revisa que haya suficiente personal para los descansos post-noche.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_v(v):
            if 'TITULAR' in v: return 'background-color: #d1fae5; color: #065f46; font-weight: bold;'
            if 'DISPONIBLE' in v: return 'background-color: #fef3c7; color: #92400e;'
            if 'LEY' in v or 'POST-NOCHE' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold;'
            return ''
        m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
        st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_v), use_container_width=True)
