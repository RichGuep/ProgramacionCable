import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - Relevos", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 50px; border: none; }
    .stTabs [aria-selected="true"] { background-color: #1a365d !important; color: white !important; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN (CORREGIDO) ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center; color:#1a365d;'>MovilGo</h1>", unsafe_allow_html=True)
            # El form debe envolver al botón obligatoriamente
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                submit = st.form_submit_button("INGRESAR")
                
                if submit:
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True
                        st.rerun()
                    else:
                        st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descanso")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo Titular Mínimo", 1, 15, 2)

    num_dias = calendar.monthrange(2025, mes_num)[1]
    semanas = {}
    for d in range(1, num_dias + 1):
        s = datetime(2025, mes_num, d).isocalendar()[1]
        if s not in semanas: semanas[s] = []
        semanas[s].append(d)

    if st.button("🚀 GENERAR MALLA CON RELEVOS"):
        prog_bar = st.progress(0)
        status = st.empty()
        
        status.text("10% - Analizando personal...")
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Final", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], semanas.keys(), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        status.text("40% - Aplicando reglas de estabilidad semanal...")
        prog_bar.progress(40)
        
        # Objetivo: Cobertura total y penalizar huecos
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 10000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for s_idx, dias_s in semanas.items():
            for _, row in df_f.iterrows():
                e = row['nombre']
                prob += lpSum([t_sem[e][s_idx][t] for t in LISTA_TURNOS]) <= 1
                for d in dias_s:
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

        for d in range(1, num_dias + 1):
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) + hueco[d][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= (num_dias - 5)
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1

        status.text("70% - Optimizando cobertura...")
        prog_bar.progress(70)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            status.text("90% - Procesando etiquetas...")
            prog_bar.progress(90)
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2025, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][d][t]) == 1: t_real = t
                    s_act = datetime(2025, mes_num, d).isocalendar()[1]
                    t_base = "AM"
                    for t in LISTA_TURNOS:
                        if value(t_sem[e][s_act][t]) == 1: t_base = t
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: df_res.at[i, 'Final'] = "DESC. LEY"
                else: df_res.at[i, 'Final'] = f"DISPONIBLE {r['Base']}"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); time.sleep(1); status.empty(); prog_bar.empty()
        else:
            st.error("No se pudo generar la malla. Revisa los cupos.")

    # --- 4. RENDERIZADO ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_v(v):
            if 'TITULAR' in v: return 'background-color: #d1fae5; color: #065f46; font-weight: bold;'
            if 'DISPONIBLE' in v: return 'background-color: #fef3c7; color: #92400e;'
            if 'LEY' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold;'
            return ''

        t1, t2, t3 = st.tabs(["📅 Malla Principal", "⚖️ Auditoría Reforma", "📊 Cobertura"])
        with t1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.applymap(style_v), use_container_width=True)
        with t2:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                desc = len(g[g['Final'] == 'DESC. LEY'])
                audit.append({"Empleado": e, "Descansos Fin de Semana": desc, "Cumple Reforma (2+2)": "✅" if desc >= 2 else "⚠️"})
            st.table(pd.DataFrame(audit))
        with t3:
            cob = df_v[df_v['Final'].str.contains('TITULAR')].copy()
            cob['Turno_Limpio'] = cob['Final'].str.replace('TITULAR ', '')
            st.dataframe(cob.groupby(['Label', 'Turno_Limpio']).size().unstack(fill_value=0), use_container_width=True)
