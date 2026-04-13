import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Compensatorios", layout="wide", page_icon="⚖️")

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
        st.header("⚙️ Parámetros")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    # Estructura de semanas para compensatorios
    semanas_lista = []
    cal = calendar.Calendar(firstweekday=0)
    for semana in cal.monthdayscalendar(2026, mes_num):
        semanas_lista.append([d for d in semana if d != 0])

    if st.button("🚀 GENERAR MALLA CON COMPENSATORIOS"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Aplicando regla de compensación inmediata (Lunes-Viernes)...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Compensatorios", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        # Variable auxiliar para marcar si trabajó fin de semana
        trabajo_fds = LpVariable.dicts("TrabajoFDS", (df_f['nombre'], range(len(semanas_lista))), cat='Binary')

        # Objetivo: Cobertura total
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_cont = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            num_fds_mes = len(semanas_lista)
            min_desc_ley = 2 if num_fds_mes <= 4 else 3
            
            # 1. Mínimo de descansos de ley en el mes
            dias_fds_contrato = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_cont]
            prob += lpSum([asig[e][d][t] for d in dias_fds_contrato for t in ["AM", "PM", "Noche"]]) <= (len(dias_fds_contrato) - min_desc_ley)

            # 2. Lógica de Compensatorio Inmediato
            for s_idx, dias_s in enumerate(semanas_lista):
                # Identificar el día de fin de semana de esta semana
                dia_fds = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_cont]
                dias_semana_siguiente = semanas_lista[s_idx + 1][:5] if s_idx + 1 < len(semanas_lista) else []

                if dia_fds:
                    d_fds = dia_fds[0]
                    # Si trabaja el FDS...
                    prob += trabajo_fds[e][s_idx] >= lpSum([asig[e][d_fds][t] for t in ["AM", "PM", "Noche"]])
                    
                    # ...debe descansar un día entre Lunes y Viernes de la semana siguiente
                    if dias_semana_siguiente:
                        prob += lpSum([asig[e][d][t] for d in dias_semana_siguiente for t in ["AM", "PM", "Noche"]]) <= (len(dias_semana_siguiente) - trabajo_fds[e][s_idx])

        # Cupos mínimos
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) >= cupo_manual

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[e][d][t]) == 1: t_real = t
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            # Post-procesamiento de etiquetas
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": 
                    df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: 
                    df_res.at[i, 'Final'] = "DESC. LEY"
                else: 
                    df_res.at[i, 'Final'] = "COMPENSATORIO"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        tab1, tab2 = st.tabs(["📅 Malla", "⚖️ Auditoría de Compensatorios"])
        
        with tab1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
            
        with tab2:
            st.subheader("Validación de Descansos Semanales")
            audit = []
            for emp, grupo in df_v.groupby("Empleado"):
                ley = len(grupo[grupo['Final'] == 'DESC. LEY'])
                comp = len(grupo[grupo['Final'] == 'COMPENSATORIO'])
                audit.append({
                    "Empleado": emp,
                    "Descansos de Ley (FDS)": ley,
                    "Compensatorios (L-V)": comp,
                    "Cumplimiento 2+2 / 3+2": "✅" if ley >= 2 else "⚠️ Revisar",
                    "Estatus": "Óptimo" if comp >= (len(semanas_lista) - ley) else "Ajustando"
                })
            st.table(pd.DataFrame(audit))
