import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Cupo Blindado", layout="wide", page_icon="🚀")

# --- 2. MOTOR ---
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
        st.header("⚙️ Parámetros de Operación")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_solicitado = st.number_input("Personal Requerido por Turno", 1, 20, 2)

    num_dias = calendar.monthrange(2025, mes_num)[1] # Ajustado a 2025
    cal = calendar.Calendar(firstweekday=0)
    semanas_lista = [ [d for d in sem if d != 0] for sem in cal.monthdayscalendar(2025, mes_num) ]

    if st.button("🚀 GENERAR MALLA (CUPO PRIORITARIO)"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Calculando cobertura obligatoria por turno...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Cupo_Blindado", LpMaximize)
        
        # Variables
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], range(len(semanas_lista)), ["AM", "PM", "Noche"]), cat='Binary')
        
        # OBJETIVO: Maximizar asignación respetando cupos
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        # --- RESTRICCIÓN 1: CUPO DIARIO OBLIGATORIO ---
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                # Obligamos a que la suma de empleados sea exactamente el cupo solicitado
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) == cupo_solicitado

        # --- RESTRICCIÓN 2: LÓGICA DE DESCANSOS Y SEGURIDAD ---
        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_cont = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) <= 1 # Máximo 1 turno al día
                
                if d < num_dias:
                    # Candado Noche y PM-AM
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Estabilidad Semanal: Misma jornada toda la semana
            for s_idx, dias_s in enumerate(semanas_lista):
                prob += lpSum([t_sem[e][s_idx][t] for t in ["AM", "PM", "Noche"]]) <= 1
                for d in dias_s:
                    for t in ["AM", "PM", "Noche"]:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

        status.text("80% - Verificando viabilidad de descansos...")
        prog_bar.progress(80)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2025, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[e][d][t]) == 1: t_real = t
                    
                    # Determinar Turno Base de la semana
                    s_act = next(i for i, sem in enumerate(semanas_lista) if d in sem)
                    t_base = "AM"
                    for t in ["AM", "PM", "Noche"]:
                        if value(t_sem[e][s_act][t]) == 1: t_base = t
                        
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": row['descanso_ley']})
            
            df_res = pd.DataFrame(res_list)
            # Etiquetas finales
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": 
                    df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: 
                    df_res.at[i, 'Final'] = "DESC. LEY"
                else: 
                    df_res.at[i, 'Final'] = f"DISPONIBLE {r['Base']}"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()
        else:
            st.error(f"IMPOSIBLE CUMPLIR CUPO: Tienes {len(df_f)} empleados para un cupo de {cupo_solicitado*3} personas diarias más descansos. Aumenta la nómina o baja el cupo.")

    # --- RENDERIZADO ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        t1, t2 = st.tabs(["📅 Malla Programada", "📊 Verificación de Cupos"])
        
        with t1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
            
        with t2:
            st.write(f"### Análisis de Cobertura (Objetivo: {cupo_solicitado} por turno)")
            cob = df_v[df_v['Final'].str.contains('TITULAR')].copy()
            cob['T'] = cob['Final'].str.replace('TITULAR ', '')
            res_cob = cob.groupby(['Label', 'T']).size().unstack(fill_value=0)
            st.dataframe(res_cob.style.highlight_between(left=cupo_solicitado, right=cupo_solicitado, color='#d1fae5'), use_container_width=True)
