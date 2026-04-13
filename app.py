import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Motor de Relevos", layout="wide")

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
        st.header("⚙️ Parámetros Operativos")
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_fijo = 2 # 2 AM, 2 PM, 2 Noche = 6 diarios
        
    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button("🚀 GENERAR MALLA DE RELEVOS"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        # MODELO: Maximizar estabilidad y cobertura
        prob = LpProblem("MovilGo_Relevos", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (empleados, range(len(semanas)), TURNOS), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (empleados, dias_rango), cat='Binary')

        # Objetivo: Priorizar que todos trabajen en su turno base
        prob += lpSum(asig[e][d][t] for e in empleados for d in dias_rango for t in TURNOS)

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # REGLA: 4 descansos al mes (1 por semana)
            prob += lpSum(es_descanso[e][d] for d in dias_rango) == 4

            for s_idx, dias_s in enumerate(semanas):
                # Un turno base por semana (Bienestar)
                prob += lpSum(t_sem[e][s_idx][t] for t in TURNOS) <= 1
                for d in dias_s:
                    for t in TURNOS:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]
                
                # Lógica Richard: Compensatorio si trabajó el día de ley
                dia_cont = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
                if dia_cont:
                    d_c = dia_cont[0]
                    # Si trabajó el FDS de ley, descansa un día de esa misma semana o la siguiente
                    prob += lpSum(es_descanso[e][d] for d in dias_s) >= lpSum(asig[e][d_c][t] for t in TURNOS)

            for d in dias_rango:
                prob += lpSum(asig[e][d][t] for t in TURNOS) + es_descanso[e][d] == 1
                # Descansos mínimos entre turnos
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # COBERTURA MÍNIMA: 2 personas por turno siempre
        for d in dias_rango:
            for t in TURNOS:
                prob += lpSum(asig[e][d][t] for e in empleados) >= cupo_fijo

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    t_asig = "---"
                    for t in TURNOS:
                        if value(asig[e][d][t]) == 1: t_asig = t
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})

            df_res = pd.DataFrame(res)
            df_res['Final'] = ""
            # Priorizar Titulares
            for (d, t), group in df_res[df_res['Turno'] != "---"].groupby(['Dia', 'Turno']):
                for i, idx in enumerate(group.index):
                    df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_fijo else f"DISPONIBLE {t}"
            
            # Marcar descansos
            for idx in df_res[df_res['Turno'] == "---"].index:
                r = df_res.loc[idx]
                dia_ley_nom = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if r['Nom_Dia'] == dia_ley_nom else "DESC. COMP."

            st.session_state['malla_final'] = df_res
            st.success("✅ Malla de Relevos calculada con éxito.")
        else:
            st.error("🚨 Error matemático: Revisa que la nómina tenga los días de ley balanceados.")

    if 'malla_final' in st.session_state:
        m_f = st.session_state['malla_final'].pivot(index="Empleado", columns="Label", values="Final")
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        
        def style_f(v):
            if 'TITULAR' in str(v): return 'background-color: #003366; color: white; font-weight: bold'
            if 'DISPONIBLE' in str(v): return 'background-color: #d4edda; color: #155724'
            if 'LEY' in str(v): return 'background-color: #ff9900; color: white'
            if 'COMP' in str(v): return 'background-color: #ffd966'
            return ''
            
        st.dataframe(m_f[cols].style.map(style_f), use_container_width=True)
