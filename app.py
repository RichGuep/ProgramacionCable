import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - Sistema Integral", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 45px; width: 100%; border: none; }
    .stTabs [aria-selected="true"] { background-color: #1a365d !important; color: white !important; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN SEGURO ---
def login():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.5, 1])
        with col_login:
            st.markdown("<br><br><h1 style='text-align:center; color:#1a365d;'>MovilGo Login</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("ACCEDER AL SISTEMA"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales no autorizadas.")
        st.stop()

login()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df.rename(columns={'nombre': 'nombre', 'cargo': 'cargo', 'descanso': 'descanso_ley'})
    except Exception as e:
        return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("Panel de Control")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_fijo = st.number_input("Cupo Titular Mínimo", 1, 10, 2)
        
    num_dias = calendar.monthrange(2026, mes_num)[1]
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    # --- 4. MOTOR ---
    if st.button("🚀 GENERAR MALLA COMPLETA"):
        prog_bar = st.progress(0)
        status = st.empty()
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Master", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (df_f['nombre'], range(1, num_dias + 1)), cat='Binary')
        
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            dias_fds = [d for d in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
            
            prob += lpSum([es_descanso[e][d] for d in dias_fds]) >= (2 if len(semanas) < 5 else 3)
            
            for s_idx, dias_s in enumerate(semanas):
                dia_cont = [d for d in dias_s if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_l_nom]
                if dia_cont and s_idx + 1 < len(semanas):
                    d_c = dia_cont[0]
                    dias_lv_sig = [dia for dia in semanas[s_idx+1] if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, dia).weekday()] not in ["Sab", "Dom"]]
                    prob += lpSum([es_descanso[e][dia] for dia in dias_lv_sig]) == lpSum([asig[e][d_c][t] for t in ["AM", "PM", "Noche"]])

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) + es_descanso[e][d] == 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in ["AM", "PM", "Noche"]]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        for d in range(1, num_dias + 1):
            for t in ["AM", "PM", "Noche"]:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) >= cupo_fijo

        prog_bar.progress(50)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
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
            for d in range(1, num_dias + 1):
                for t in ["AM", "PM", "Noche"]:
                    idxs = df_res[(df_res['Dia'] == d) & (df_res['Turno'] == t)].index
                    for i, idx in enumerate(idxs):
                        df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_fijo else f"DISPONIBLE {t}"
            
            for idx in df_res[df_res['Turno'] == "---"].index:
                dia_ley_nom = "Sab" if "sab" in str(df_res.at[idx, 'Ley']).lower() else "Dom"
                df_res.at[idx, 'Final'] = "DESC. LEY" if df_res.at[idx, 'Nom_Dia'] == dia_ley_nom else "DESC. COMP."
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100)
            status.empty()
            prog_bar.empty()
        else:
            st.error("🚨 Imposible cumplir cupos.")

    # --- 5. RENDERIZADO ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        tab1, tab2, tab3 = st.tabs(["📅 Malla Maestra", "⚖️ Auditoría", "📊 Cobertura"])
        
        with tab1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            def color_malla(v):
                if 'TITULAR' in v: return 'background-color: #cce5ff; color: #004085; font-weight: bold'
                if 'DISPONIBLE' in v: return 'background-color: #d4edda; color: #155724'
                if 'LEY' in v: return 'background-color: #ff9900; color: white'
                if 'COMP' in v: return 'background-color: #ffd966'
                return ''
            st.dataframe(m_f[cols].style.map(color_malla), use_container_width=True)
            
        with tab2:
            audit = []
            for emp, grupo in df_v.groupby("Empleado"):
                ley = len(grupo[grupo['Final'] == 'DESC. LEY'])
                comp = len(grupo[grupo['Final'] == 'DESC. COMP.'])
                audit.append({"Empleado": emp, "Ley": ley, "Compensatorios": comp, "Total": ley + comp})
            st.table(pd.DataFrame(audit))
            
        with tab3:
            st.write("#### Personal por Día (Titulares)")
            cob_diaria = df_v[df_v['Final'].str.contains('TITULAR')].groupby('Label').size()
            st.bar_chart(cob_diaria)
