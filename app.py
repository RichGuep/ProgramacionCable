import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - ZMO Master", layout="wide", page_icon="⚙️")

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
            st.markdown("<h1 style='text-align:center; color:#1a365d;'>MovilGo Login</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("ACCEDER"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login()

# --- 3. CARGA DE DATOS (FLEXIBLE) ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        # Limpieza de columnas para evitar errores de "Empresa" o "Empresa!"
        df.columns = df.columns.str.strip().str.lower().str.replace('!', '', regex=False)
        return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("🏢 Filtros de Operación")
        lista_emp = sorted(df_raw['empresa'].unique())
        empresa_sel = st.selectbox("Seleccione Empresa/ZMO", lista_emp)
        
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes de Programación", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        df_emp = df_raw[df_raw['empresa'] == empresa_sel]
        cargo_sel = st.selectbox("Cargo", sorted(df_emp['cargo'].unique()))

    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    ROLES = ["Control", "Patio", "Inspector Noche", "Apoyo"]

    if st.button(f"🚀 GENERAR MALLA DEFINITIVA - {empresa_sel.upper()}"):
        df_f = df_emp[df_emp['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        if len(empleados) < 7:
            st.warning(f"Se detectaron {len(empleados)} técnicos. La lógica óptima es con 7.")

        prob = LpProblem("ZMO_Final", LpMaximize)
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS, ROLES), cat='Binary')
        
        # Variable para Inspector Dom-Vie (6 noches fijas)
        semanas_dom = [d for d in dias_rango if datetime(2026, mes_num, d).weekday() == 6]
        es_inspector_sem = LpVariable.dicts("EsInspSem", (empleados, semanas_dom), cat='Binary')

        prob += lpSum(asig[e][d][t][r] for e in empleados for d in dias_rango for t in TURNOS for r in ROLES)

        for e in empleados:
            for dom in semanas_dom:
                ciclo_inspector = [d for d in range(dom, min(dom + 6, num_dias + 1))]
                for d in ciclo_inspector:
                    # El Inspector Noche trabaja de Dom a Vie
                    prob += asig[e][d]["Noche"]["Inspector Noche"] == es_inspector_sem[e][dom]
                
                # Si es inspector, descansa el Sábado (dom + 6)
                if dom + 6 <= num_dias:
                    prob += lpSum(asig[e][dom+6][t][r] for t in TURNOS for r in ROLES) <= (1 - es_inspector_sem[e][dom])
            
            # Solo 1 inspector por semana en todo el equipo
            for dom in semanas_dom:
                prob += lpSum(es_inspector_sem[emp][dom] for emp in empleados) == 1

            for d in dias_rango:
                prob += lpSum(asig[e][d][t][r] for t in TURNOS for r in ROLES) <= 1
                if d < num_dias: # Seguridad Industrial
                    prob += lpSum(asig[e][d]["Noche"][r] for r in ROLES) + lpSum(asig[e][d+1]["AM"][r] for r in ROLES) <= 1

        # COBERTURA DIARIA POR ROL
        for d in dias_rango:
            dn_idx = datetime(2026, mes_num, d).weekday() # 5=Sab, 6=Dom
            for t in TURNOS:
                prob += lpSum(asig[e][d][t]["Control"] for e in empleados) == 1
                # Patio L-V, FDS con Seniors
                if dn_idx < 5:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 1
                else:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 0
            
            # 1 Apoyo técnico AM de Lunes a Viernes
            if dn_idx < 5:
                prob += lpSum(asig[e][d]["AM"]["Apoyo"] for e in empleados) == 1

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    t_final = "---"
                    for t in TURNOS:
                        for r in ROLES:
                            if value(asig[e][d][t][r]) == 1: t_final = f"{t} ({r})"
                    
                    if t_final == "---":
                        t_final = "DESC. LEY" if dn == "Dom" else "DESC. COMP."
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Empleado": e, "Turno": t_final})

            df_res = pd.DataFrame(res)
            m_f = df_res.pivot(index="Empleado", columns="Label", values="Turno")
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            
            def style_zmo(v):
                if 'Control' in str(v): return 'background-color: #003366; color: white; font-weight: bold'
                if 'Patio' in str(v): return 'background-color: #1e88e5; color: white'
                if 'Inspector' in str(v): return 'background-color: #6a1b9a; color: white'
                if 'Apoyo' in str(v): return 'background-color: #2e7d32; color: white'
                if 'DESC' in str(v): return 'background-color: #f1f1f1; color: #888'
                return ''

            st.write(f"### Malla Programada: {empresa_sel.upper()}")
            st.dataframe(m_f[cols].style.map(style_zmo), use_container_width=True)
            st.info("💡 Fines de Semana: Los turnos de Patio están libres para cobertura con Operadores Senior.")
        else: st.error("No se encontró solución. Revisa la cantidad de personal.")
