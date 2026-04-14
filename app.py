import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - ZMO Full", layout="wide")

# --- CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower().str.replace('!', '')
        return df
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("🏢 Configuración ZMO")
        empresa_sel = st.selectbox("Empresa / ZMO", sorted(df_raw['empresa'].unique()))
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        df_emp = df_raw[df_raw['empresa'] == empresa_sel]
        cargo_sel = st.selectbox("Cargo", sorted(df_emp['cargo'].unique()))

    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    ROLES_CORE = ["Control", "Patio"]
    ROLES_EXTRA = ["Inspector Noche", "Apoyo Técnico"]

    if st.button(f"🚀 GENERAR MALLA DEFINITIVA {empresa_sel.upper()}"):
        df_f = df_emp[df_emp['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        prob = LpProblem("ZMO_Final_Logic", LpMaximize)
        
        # Variables: Empleado, Día, Turno, Rol
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS, ROLES_CORE + ROLES_EXTRA), cat='Binary')
        
        # Objetivo: Estabilidad y cobertura total
        prob += lpSum(asig[e][d][t][r] for e in empleados for d in dias_rango for t in TURNOS for r in ROLES_CORE + ROLES_EXTRA)

        # Semanas para la rotación del "Sobrante"
        cal = calendar.Calendar(firstweekday=0)
        semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

        for e in empleados:
            for d in dias_rango:
                # Un solo rol por día
                prob += lpSum(asig[e][d][t][r] for t in TURNOS for r in ROLES_CORE + ROLES_EXTRA) <= 1
                
                # Seguridad Industrial
                if d < num_dias:
                    # No Noche a AM
                    prob += lpSum(asig[e][d]["Noche"][r] for r in ROLES_CORE + ROLES_EXTRA) + \
                            lpSum(asig[e][d+1]["AM"][r] for r in ROLES_CORE + ROLES_EXTRA) <= 1

        for d in dias_rango:
            dn_idx = datetime(2026, mes_num, d).weekday()
            for t in TURNOS:
                # 1. SIEMPRE 1 Técnico de CONTROL (AM, PM, Noche)
                prob += lpSum(asig[e][d][t]["Control"] for e in empleados) == 1
                
                # 2. PATIO: 1 de Lunes a Viernes. FDS = 0 (Entran Seniors)
                if dn_idx < 5:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 1
                else:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 0

            # 3. ASIGNACIÓN DEL "SOBRANTE" (Lunes a Viernes)
            if dn_idx < 5:
                prob += lpSum(asig[e][d]["Noche"]["Inspector Noche"] for e in empleados) == 1
                prob += lpSum(asig[e][d]["AM"]["Apoyo Técnico"] for e in empleados) == 1

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    t_final = "---"
                    for t in TURNOS:
                        for r in ROLES_CORE + ROLES_EXTRA:
                            if value(asig[e][d][t][r]) == 1:
                                t_final = f"{t} ({r})"
                    
                    if t_final == "---":
                        t_final = "DESC. LEY" if dn == "Dom" else "DESC. COMP."
                        
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Empleado": e, "Turno": t_final})

            df_res = pd.DataFrame(res)
            m_f = df_res.pivot(index="Empleado", columns="Label", values="Turno")
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            
            def style_final(v):
                if 'Control' in str(v): return 'background-color: #003366; color: white'
                if 'Patio' in str(v): return 'background-color: #1e88e5; color: white'
                if 'Inspector' in str(v): return 'background-color: #6a1b9a; color: white' # Morado para Inspector
                if 'Apoyo' in str(v): return 'background-color: #2e7d32; color: white' # Verde para Apoyo
                if 'DESC' in str(v): return 'background-color: #eeeeee; color: #999999'
                return ''

            st.dataframe(m_f[cols].style.map(style_final), use_container_width=True)
            st.success("✅ Malla generada: 1 Control, 1 Patio (L-V), 1 Inspector Noche y 1 Apoyo Técnico.")
