import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Semanal", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 52px; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    col1, col_login, col3 = st.columns([1, 1.8, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
        user = st.text_input("Usuario")
        pwd = st.text_input("Clave", type="password")
        if st.button("INGRESAR"):
            if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                st.session_state['auth'] = True; st.rerun()
    st.stop()

# --- 4. MOTOR DE OPTIMIZACIÓN SEMANAL ---
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
        ano_sel = 2025
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo Operativo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    
    # Agrupar días por semanas del calendario
    semanas = {}
    for d in range(1, num_dias + 1):
        sem_num = datetime(ano_sel, mes_num, d).isocalendar()[1]
        if sem_num not in semanas: semanas[sem_num] = []
        semanas[sem_num].append(d)

    if st.button("🚀 GENERAR MALLA POR TURNOS SEMANALES"):
        prog = st.progress(0); status = st.empty()
        status.text("Aplicando restricciones de Jornada Semanal Única...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Semanal", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        # Variable que define el turno de la persona para TODA la semana
        turno_sem = LpVariable.dicts("TSem", (df_f['nombre'], semanas.keys(), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # OBJETIVO: Cobertura máxima
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 1000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for s_idx, dias_sem in semanas.items():
            for _, row in df_f.iterrows():
                e = row['nombre']
                # Una persona solo puede tener UN tipo de turno asignado en la semana
                prob += lpSum([turno_sem[e][s_idx][t] for t in LISTA_TURNOS]) <= 1
                
                for d in dias_sem:
                    for t in LISTA_TURNOS:
                        # Si trabaja el día D en turno T, ese DEBE ser el turno de su semana
                        prob += asig[e][d][t] <= turno_sem[e][s_idx][t]

        # Cupos y Descansos
        for d in range(1, num_dias + 1):
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) + hueco[d][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            # Límite de 4-5 descansos
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= (num_dias - 5)
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1

        prog.progress(50)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=40))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for d in range(1, num_dias + 1):
                label = f"{d} - {['Lun','Mar','Mie','Jue','Vie','Sab','Dom'][datetime(ano_sel, mes_num, d).weekday()]}"
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][d][t]) == 1: t_asig = t
                    
                    # Determinar el turno base de su semana para el DISPONIBLE
                    sem_act = datetime(ano_sel, mes_num, d).isocalendar()[1]
                    t_base = "AM"
                    for t in LISTA_TURNOS:
                        if value(turno_sem[e][sem_act][t]) == 1: t_base = t
                    
                    res_list.append({"Dia": d, "Label": label, "Empleado": e, "Turno": t_asig, "Turno_Semana": t_base, "Ley": row['descanso_ley']})
            
            df_res = pd.DataFrame(res_list)
            # Post-procesamiento para etiquetas
            for i, row in df_res.iterrows():
                if row['Turno'] == "---":
                    dia_nom = row['Label'].split(" - ")[1]
                    dia_ley = "Sab" if "sab" in str(row['Ley']).lower() else "Dom"
                    if dia_nom == dia_ley: df_res.at[i, 'Turno'] = "DESC. LEY"
                    else: df_res.at[i, 'Turno'] = f"DISPONIBLE {row['Turno_Semana']}"
            
            st.session_state['df_final'] = df_res
            prog.progress(100); status.empty(); time.sleep(1); prog.empty()

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Turno')
        st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
