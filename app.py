import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Estabilidad Laboral", layout="wide", page_icon="🧘")

# --- 2. LOGIN ---
def login():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.5, 1])
        with col_login:
            st.markdown("<h1 style='text-align:center;'>MovilGo Login</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
        st.stop()

login()

# --- 3. CARGA DE DATOS ---
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
        cupo_obj = 2 
        
    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    
    # Estructura de semanas
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button("🚀 GENERAR MALLA CON ESTABILIDAD"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        prob = LpProblem("MovilGo_Stability", LpMaximize)
        
        # Variables: Asignación, Descanso y Turno Semanal (para estabilidad)
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (empleados, range(len(semanas)), TURNOS), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (empleados, dias_rango), cat='Binary')

        # Objetivo: Maximizar asignaciones útiles
        prob += lpSum(asig[e][d][t] for e in empleados for d in dias_rango for t in TURNOS)

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # --- REGLA: 1 TURNO FIJO POR SEMANA ---
            for s_idx, dias_s in enumerate(semanas):
                # Solo un turno base por semana
                prob += lpSum(t_sem[e][s_idx][t] for t in TURNOS) <= 1
                for d in dias_s:
                    for t in TURNOS:
                        # Si trabaja, debe ser el turno base de esa semana
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]
                
                # --- LÓGICA COMPENSATORIA ---
                dia_cont = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
                if dia_cont and s_idx + 1 < len(semanas):
                    d_c = dia_cont[0]
                    dias_lv_sig = [dia for dia in semanas[s_idx+1] if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, dia).weekday()] not in ["Sab", "Dom"]]
                    # Si trabaja el día de ley, descansa un día de la semana siguiente
                    prob += lpSum(es_descanso[e][dia] for dia in dias_lv_sig) == lpSum(asig[e][d_c][t] for t in TURNOS)

            # --- SEGURIDAD Y CICLO ---
            for d in dias_rango:
                prob += lpSum(asig[e][d][t] for t in TURNOS) + es_descanso[e][d] == 1
                if d < num_dias:
                    # Noche -> Descanso Obligatorio (no AM, no PM, no Noche)
                    prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                    # PM -> No AM al día siguiente
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # COBERTURA MÍNIMA
        for d in dias_rango:
            for t in TURNOS:
                prob += lpSum(asig[e][d][t] for e in empleados) >= cupo_obj

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    t_asig = "---"; s_act = next(i for i, sem in enumerate(semanas) if d in sem)
                    for t in TURNOS:
                        if value(asig[e][d][t]) == 1: t_asig = t
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})

            df_res = pd.DataFrame(res)
            df_res['Final'] = ""
            for (d, t), group in df_res[df_res['Turno'] != "---"].groupby(['Dia', 'Turno']):
                for i, idx in enumerate(group.index):
                    df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_obj else f"DISPONIBLE {t}"
            
            for idx in df_res[df_res['Turno'] == "---"].index:
                dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."

            st.session_state['malla'] = df_res
            st.success("✅ Malla generada con estabilidad semanal y relevos.")
        else:
            st.error("No se pudo cuadrar la estabilidad con el personal actual.")

    if 'malla' in st.session_state:
        m_f = st.session_state['malla'].pivot(index="Empleado", columns="Label", values="Final")
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        def style_f(v):
            if 'TITULAR' in str(v): return 'background-color: #003366; color: white; font-weight: bold'
            if 'DISPONIBLE' in str(v): return 'background-color: #d4edda; color: #155724'
            if 'LEY' in str(v): return 'background-color: #ff9900; color: white'
            if 'COMP' in str(v): return 'background-color: #ffd966'
            return ''
        st.dataframe(m_f[cols].style.map(style_f), use_container_width=True)
