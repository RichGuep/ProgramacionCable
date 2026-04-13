import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Ley Laboral Primero", layout="wide", page_icon="⚖️")

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

    if st.button("🚀 GENERAR MALLA (LEY LABORAL ESTRICTA)"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Calculando descansos de ley obligatorios...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Strict_Law", LpMaximize)
        
        # Variables
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], range(len(semanas)), ["AM", "PM", "Noche"]), cat='Binary')
        
        # Objetivo: Maximizar estabilidad y cumplimiento
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley_cont = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            min_desc = 3 if len(semanas) >= 5 else 2
            
            # --- REGLA 1: DESCANSOS DE LEY OBLIGATORIOS ---
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley_cont]
            # Obligamos a que el número de días trabajados en FDS sea (Total FDS - Minimo Descanso)
            prob += lpSum([asig[e][d][t] for d in dias_fds for t in ["AM", "PM", "Noche"]]) == (len(dias_fds) - min_desc)

            # --- REGLA 2: COMPENSATORIO INMEDIATO ---
            for s_idx, dias_s in enumerate(semanas):
                dia_fds_sem = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley_cont]
                if dia_fds_sem:
                    d_f = dia_fds_sem[0]
                    lunes_siguiente = semanas[s_idx+1][0] if s_idx+1 < len(semanas) else None
                    if lunes_siguiente:
                        # Si trabaja el finde (asig=1), el lunes DEBE ser 0 (descanso)
                        prob += lpSum([asig[e][d_f][t] for t in ["AM", "PM", "Noche"]]) + lpSum([asig[e][lunes_siguiente][t] for t in ["AM", "PM", "Noche"]]) <= 1

            # --- REGLA 3: SEGURIDAD ---
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # --- REGLA 4: CUPO ---
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) == cupo_solicitado

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=80))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[e][d][t]) == 1: t_real = t
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            # Procesar etiquetas
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: df_res.at[i, 'Final'] = "DESC. LEY"
                else: df_res.at[i, 'Final'] = "DESC. COMPENSATORIO"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()
        else:
            st.error("🚨 ERROR CRÍTICO: No hay personal suficiente para cubrir el cupo Y dar los descansos de ley. Por favor, baja el cupo o revisa la nómina.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        tab1, tab2 = st.tabs(["📅 Malla", "⚖️ Auditoría (Ley vs Real)"])
        with tab1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
        with tab2:
            audit = []
            for emp, grupo in df_v.groupby("Empleado"):
                audit.append({
                    "Empleado": emp,
                    "Descansos Ley (FDS)": len(grupo[grupo['Final'] == 'DESC. LEY']),
                    "Compensatorios (Semana)": len(grupo[grupo['Final'] == 'DESC. COMPENSATORIO']),
                    "Total Descansos": len(grupo[grupo['Final'].str.contains('DESC')]),
                    "Estado": "✅ CORRECTO" if len(grupo[grupo['Final'] == 'DESC. LEY']) >= 2 else "❌ REVISAR"
                })
            st.table(pd.DataFrame(audit))
