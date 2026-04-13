import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Rotación Richard", layout="wide", page_icon="🔄")

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
        cupo_fijo = 2 # Según tu instrucción para tener 6 trabajando (2x3 turnos)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button("🚀 GENERAR MALLA (ROTACIÓN 2x2)"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Rotacion_Richard", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (df_f['nombre'], range(1, num_dias + 1)), cat='Binary')
        
        # Objetivo
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        # REGLA 1: Cupo exacto de 2 por turno cada día
        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) == cupo_fijo

        # REGLA 2: Lógica de Grupos y Rotación
        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
            
            # Obligar a descansar exactamente 2 fines de semana al mes (Rotación 1 sí, 1 no)
            prob += lpSum([es_descanso[e][d] for d in dias_fds]) == 2
            
            # Evitar que descansen dos fines de semana seguidos
            for i in range(len(dias_fds)-1):
                prob += es_descanso[e][dias_fds[i]] + es_descanso[e][dias_fds[i+1]] <= 1

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) + es_descanso[e][d] == 1
                
                # Compensatorios: Si trabajó su fds de ley, debe descansar un día L-V de la sig. semana
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                if dn == dia_l_nom:
                    # Encontrar la semana siguiente
                    s_idx = next(i for i, sem in enumerate(semanas) if d in sem)
                    if s_idx + 1 < len(semanas):
                        dias_lv_sig = [dia for dia in semanas[s_idx+1] if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, dia).weekday()] not in ["Sab", "Dom"]]
                        prob += lpSum([es_descanso[e][dia] for dia in dias_lv_sig]) >= lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]])

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=40))

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
            df_res['Final'] = ""
            for idx in df_res.index:
                t = df_res.at[idx, 'Turno']
                if t != "---":
                    df_res.at[idx, 'Final'] = f"TITULAR {t}"
                else:
                    dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                    df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."
            
            st.session_state['df_final'] = df_res
        else:
            st.error("🚨 La rotación 2x2 es matemáticamente ajustada. Revisa que tengas exactamente 4 Sábados y 4 Domingos en la lista de empleados.")

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Final')
        st.dataframe(m_f.style.map(lambda v: 'background-color: #ff9900; color: white' if 'DESC' in str(v) else 'background-color: #cce5ff' if 'TITULAR' in str(v) else ''), use_container_width=True)
