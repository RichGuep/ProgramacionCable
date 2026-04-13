import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Descansos Reales", layout="wide", page_icon="⚖️")

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

    if st.button("🚀 GENERAR MALLA CON DESCANSOS OBLIGATORIOS"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Forzando descansos legales y compensatorios...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        num_empleados = len(df_f)
        prob = LpProblem("MovilGo_Forced_Rest", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        
        # OBJETIVO: Priorizar el descanso (darle valor al hecho de NO trabajar)
        # Maximizamos la cobertura pero penalizamos el exceso de trabajo
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley_cont = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # --- LA REGLA DE ORO (IGUALDAD ESTRICTA) ---
            # Cada empleado DEBE trabajar exactamente num_dias - 4. 
            # Esto FORZA a que aparezcan 4 días de "---" (descansos) en la malla.
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]]) == (num_dias - 4)

            # --- DESCANSOS DE FIN DE SEMANA (Mínimo 2) ---
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley_cont]
            prob += lpSum([asig[e][d][t] for d in dias_fds for t in ["AM", "PM", "Noche"]]) == (len(dias_fds) - 2)

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) <= 1
                if d < num_dias:
                    # Candados de seguridad
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # CUPO OPERATIVO
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
            
            # --- ETIQUETADO DE DESCANSOS ---
            for idx in df_res.index:
                if df_res.at[idx, 'Turno'] == "---":
                    dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                    if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom:
                        df_res.at[idx, 'Final'] = "DESC. LEY"
                    else:
                        df_res.at[idx, 'Final'] = "COMPENSATORIO"
                else:
                    df_res.at[idx, 'Final'] = df_res.at[idx, 'Turno']
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()
        else:
            st.error(f"🚨 IMPOSIBLE: Para un cupo de {cupo_solicitado} personas por turno con 4 descansos cada una, necesitas al menos {int((cupo_solicitado*3*num_dias)/(num_dias-4))+1} empleados. Revisa tu nómina.")

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Final')
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        
        # Estilo para que veas los descansos resaltados
        st.dataframe(m_f[cols].style.map(lambda v: 'background-color: #ff9900; color: white; font-weight: bold' if 'DESC' in str(v) or 'COMP' in str(v) else ''), use_container_width=True)
        
        # Auditoría de cumplimiento
        st.write("### ⚖️ Auditoría de Descansos (Deberían ser 4 por persona)")
        audit = st.session_state['df_final'][st.session_state['df_final']['Final'].str.contains('DESC') | st.session_state['df_final']['Final'].str.contains('COMP')].groupby('Empleado').size()
        st.table(audit)
