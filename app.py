import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - Relevos", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.8, 1])
    with col_login:
        st.title("MovilGo")
        user = st.text_input("Usuario")
        pwd = st.text_input("Clave", type="password")
        if st.form_submit_button("INGRESAR") or (user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026"):
            st.session_state['auth'] = True; st.rerun()
    st.stop()

# --- 4. MOTOR CON LÓGICA DE RELEVOS ---
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
        cupo_manual = st.number_input("Cupo Titular Mínimo", 1, 15, 2)

    num_dias = calendar.monthrange(2025, mes_num)[1]
    semanas = {}
    for d in range(1, num_dias + 1):
        s = datetime(2025, mes_num, d).isocalendar()[1]
        if s not in semanas: semanas[s] = []
        semanas[s].append(d)

    if st.button("🚀 GENERAR MALLA CON RELEVOS"):
        prog = st.progress(0); status = st.empty()
        status.text("Calculando turnos titulares y relevos disponibles...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Relevos", LpMaximize)
        
        # Variables: Asignación real y Turno base semanal
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], semanas.keys(), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # Objetivo: Maximizar cobertura y estabilidad
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 5000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        # Restricciones
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
            # Asegurar 4 descansos de ley
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= (num_dias - 5)
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=40))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
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
                    
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": row['descanso_ley']})
            
            df_res = pd.DataFrame(res_list)
            
            # --- LÓGICA DE RELEVOS: Titular vs Disponible ---
            for i, r in df_res.iterrows():
                dia_nom = r['Label'].split(" - ")[1]
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                
                if r['Turno'] != "---":
                    df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                else:
                    if dia_nom == dia_ley:
                        df_res.at[i, 'Final'] = "DESC. LEY"
                    else:
                        # Si no es descanso de ley y no tiene turno, es el RELEVO (Disponible)
                        df_res.at[i, 'Final'] = f"DISPONIBLE {r['Base']}"
            
            st.session_state['df_final'] = df_res
            prog.progress(100); status.empty(); time.sleep(1); prog.empty()

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Final')
        
        def color_relevos(val):
            if 'TITULAR' in val: return 'background-color: #d1fae5; color: #065f46; font-weight: bold;'
            if 'DISPONIBLE' in val: return 'background-color: #fef3c7; color: #92400e;'
            if 'LEY' in val: return 'background-color: #fee2e2; color: #991b1b;'
            return ''

        st.dataframe(m_f.style.applymap(color_relevos), use_container_width=True)
        st.info("💡 **TITULAR**: Personal programado para cubrir el cupo. | **DISPONIBLE**: Personal de relevo para cubrir descansos.")
