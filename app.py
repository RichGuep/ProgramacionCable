import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - Freeway Final", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 45px; border: none; }
    .stTabs [aria-selected="true"] { background-color: #1a365d !important; color: white !important; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
def login():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.5, 1])
        with col_login:
            st.markdown("<br><h1 style='text-align:center; color:#1a365d;'>MovilGo Login</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else:
                        st.error("Credenciales Incorrectas")
        st.stop()

login()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})
    except Exception: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_obj = st.number_input("Cupo Objetivo por Turno", 1, 10, 2)
        
    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]

    if st.button("🚀 GENERAR PROGRAMACIÓN FREEWAY"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        # Modelo con Holgura para evitar el error de "Imposible"
        prob = LpProblem("Freeway_Final", LpMinimize)
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (dias_rango, TURNOS), lowBound=0, cat='Integer')

        # Objetivo: Minimizar huecos en el cupo
        prob += lpSum(hueco[d][t] * 1000 for d in dias_rango for t in TURNOS)

        for d in dias_rango:
            for t in TURNOS:
                prob += lpSum(asig[e][d][t] for e in empleados) + hueco[d][t] >= cupo_obj

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            fds_dias = [d for d in dias_rango if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley]
            
            for d in dias_rango:
                prob += lpSum(asig[e][d][t] for t in TURNOS) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Rotación de Ley: Exactamente 2 descansos de ley al mes
            prob += lpSum(asig[e][d][t] for d in fds_dias for t in TURNOS) == (len(fds_dias) - 2)

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
            
            # Asignar etiquetas Finales
            for (d, t), group in df_res[df_res['Turno'] != "---"].groupby(['Dia', 'Turno']):
                for i, idx in enumerate(group.index):
                    df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_obj else f"DISPONIBLE {t}"
            
            for idx in df_res[df_res['Turno'] == "---"].index:
                r = df_res.loc[idx]
                dia_ley_nom = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if r['Nom_Dia'] == dia_ley_nom else "DESC. COMP."

            st.session_state['malla'] = df_res
            st.success("✅ Malla procesada")

    if 'malla' in st.session_state:
        df_v = st.session_state['malla']
        t1, t2 = st.tabs(["📅 Malla Maestra", "📊 Auditoría"])
        
        with t1:
            m_f = df_v.pivot(index="Empleado", columns="Label", values="Final")
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            
            def color_f(v):
                if 'TITULAR' in str(v): return 'background-color: #003366; color: white; font-weight: bold'
                if 'DISPONIBLE' in str(v): return 'background-color: #d4edda; color: #155724'
                if 'LEY' in str(v): return 'background-color: #ff9900; color: white'
                if 'COMP' in str(v): return 'background-color: #ffd966'
                return ''
                
            # CORRECCIÓN: Se usa .map() en lugar de .applymap()
            st.dataframe(m_f[cols].style.map(color_f), use_container_width=True)
            
        with t2:
            st.subheader("Resumen de Descansos")
            audit = df_v[df_v['Final'].str.contains('DESC')].groupby(['Empleado', 'Final']).size().unstack(fill_value=0)
            st.table(audit)
