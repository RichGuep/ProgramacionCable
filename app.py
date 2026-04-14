import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS CORPORATIVOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .login-box { background-color: #ffffff; padding: 45px; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }
    h1.movilgo-title { color: #1a365d; font-weight: 800; text-transform: uppercase; letter-spacing: 5px; text-align: center; font-size: 3.2rem !important; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 52px; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if os.path.exists("logo_movilgo.png"): st.image("logo_movilgo.png", use_container_width=True)
            else: st.markdown("<h1 class='movilgo-title'>MovilGo</h1>", unsafe_allow_html=True)
            st.markdown("<div class='login-box'>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

login_page()

# --- 4. MOTOR Y LÓGICA ---
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
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)
        peso_estabilidad = st.slider("Estabilidad de Turno", 1, 50, 30)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]

    if st.button("🚀 GENERAR MALLA OPTIMIZADA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        nombres = df_f['nombre'].tolist()
        
        prob = LpProblem("MovilGo_Block_Night", LpMaximize)
        asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
        mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
        
        # Objetivo: Max asignación + Estabilidad (para fomentar bloques del mismo turno)
        prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

        for d in dias_range:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

        for e in nombres:
            row = df_f[df_f['nombre'] == e].iloc[0]
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in dias_range:
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d > 1:
                    for t in LISTA_TURNOS:
                        prob += mantiene[e][d][t] <= asig[e][d][t]
                        prob += mantiene[e][d][t] <= asig[e][d-1][t]

                # --- NUEVA LÓGICA DE NOCHE ---
                if d < num_dias:
                    # SI trabaja noche hoy (d), NO puede hacer AM ni PM mañana (d+1). 
                    # Pero SI puede volver a trabajar de Noche.
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    # Protección PM a AM
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)
            prob += lpSum([asig[e][d][t] for d in dias_range for t in LISTA_TURNOS]) >= 17

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for d_idx in dias_info:
                for e in nombres:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][d_idx["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": d_idx["n"], "Label": d_idx["label"], "Nom_Dia": d_idx["nombre"], "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_l = "Sab" if "sab" in str(grupo['Ley'].iloc[0]).lower() else "Dom"
                
                # 1. Descansos Ley
                idx_fijos = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_l)].head(2).index
                grupo.loc[idx_fijos, 'Turno'] = 'DESC. LEY'
                
                # 2. Compensatorios
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_l) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, r_f in findes_trab.iterrows():
                    hueco = grupo[(grupo['Dia'] > r_f['Dia']) & (grupo['Dia'] <= r_f['Dia'] + 7) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                    if not hueco.empty: grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'

                # 3. Post-Noche solo al finalizar el bloque de noches
                for i in range(len(grupo)-1):
                    # Si hoy fue noche y mañana está libre (---), es un descanso post-noche legítimo
                    if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                        grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final)
            st.success("✅ Malla Generada: Noches consecutivas permitidas.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_map(v):
            if v == 'DESC. LEY': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if v == 'DESC. COMPENSATORIO': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if v == 'DESC. POST-NOCHE': return 'background-color: #d1fae5; color: #065f46; font-weight: bold'
            if v == 'DISPONIBILIDAD': return 'background-color: #f1f5f9; color: #64748b'
            if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
            if v in ['AM', 'PM']: return 'background-color: #ffffff; color: #1e293b; border: 1px solid #e2e8f0'
            return ''

        m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
        cols = sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))
        st.dataframe(m_f[cols].style.map(style_map), use_container_width=True)
