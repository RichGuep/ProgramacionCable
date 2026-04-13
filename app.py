import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Greenmovil Ejecución", layout="wide")

# --- LOGIN (Simplificado para brevedad) ---
if 'auth' not in st.session_state: st.session_state['auth'] = True # Saltamos login para esta prueba

# --- CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.replace('!', '', regex=False).str.lower()
        return df
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("🏢 Greenmovil - Ejecución")
        empresa_sel = "greenmovil" 
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        df_g = df_raw[df_raw['empresa'] == empresa_sel]
        cargo_sel = st.selectbox("Cargo", sorted(df_g['cargo'].unique()))
        
        st.info("💡 Nota: Fines de semana se libera cupo de Patio para Operadores Senior.")

    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    TURNOS = ["AM", "PM", "Noche"]
    ROLES = ["Control", "Patio"] # 2 de cada uno = 4 por turno
    
    cal = calendar.Calendar(firstweekday=0)
    semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

    if st.button(f"🚀 GENERAR MALLA EJECUCIÓN"):
        df_f = df_g[df_g['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        prob = LpProblem("Greenmovil_Ejecucion", LpMaximize)
        
        # Variables
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS, ROLES), cat='Binary')
        es_descanso = LpVariable.dicts("EsDescanso", (empleados, dias_rango), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (empleados, range(len(semanas)), TURNOS), cat='Binary')

        # Objetivo: Maximizar estabilidad
        prob += lpSum(asig[e][d][t][r] for e in empleados for d in dias_rango for t in TURNOS for r in ROLES)

        for e in empleados:
            # 1. Garantizar mínimo 2 domingos de descanso al mes
            domingos = [d for d in dias_rango if datetime(2026, mes_num, d).weekday() == 6]
            prob += lpSum(es_descanso[e][d] for d in domingos) >= 2
            
            # 2. Estabilidad semanal y reglas de descanso
            for s_idx, dias_s in enumerate(semanas):
                prob += lpSum(t_sem[e][s_idx][t] for t in TURNOS) <= 1
                for d in dias_s:
                    prob += lpSum(asig[e][d][t][r] for t in TURNOS for r in ROLES) + es_descanso[e][d] == 1
                    for t in TURNOS:
                        prob += lpSum(asig[e][d][t][r] for r in ROLES) <= t_sem[e][s_idx][t]

            # 3. Seguridad Industrial (No Noche -> AM, No PM -> AM)
            for d in dias_rango[:-1]:
                prob += lpSum(asig[e][d]["Noche"][r] for r in ROLES) + lpSum(asig[e][d+1][t][r] for t in TURNOS for r in ROLES) <= 1
                prob += lpSum(asig[e][d]["PM"][r] for r in ROLES) + lpSum(asig[e][d+1]["AM"][r] for r in ROLES) <= 1

        # 4. COBERTURA POR ROL Y APOYO SENIOR
        for d in dias_rango:
            es_fds = datetime(2026, mes_num, d).weekday() >= 5 # Sábado o Domingo
            for t in TURNOS:
                # Control siempre necesita 2 (AM, PM, Noche)
                prob += lpSum(asig[e][d][t]["Control"] for e in empleados) == 2
                
                # Patio necesita 2, pero en FDS (AM/PM) se cubre con Senior (cupo 0 en la malla de técnicos)
                if es_fds and t in ["AM", "PM"]:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 0
                else:
                    prob += lpSum(asig[e][d][t]["Patio"] for e in empleados) == 2

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res = []
            for d in dias_rango:
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in empleados:
                    final_t = "---"
                    for t in TURNOS:
                        for r in ROLES:
                            if value(asig[e][d][t][r]) == 1:
                                final_t = f"{t} ({r})"
                    
                    if final_t == "---":
                        final_t = "DESC. DOMINGO" if dn == "Dom" else "DESC. COMP."
                        
                    res.append({"Dia": d, "Label": f"{d}-{dn}", "Empleado": e, "Turno": final_t, "EsFDS": dn in ["Sab", "Dom"]})

            df_res = pd.DataFrame(res)
            m_f = df_res.pivot(index="Empleado", columns="Label", values="Turno")
            cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
            
            def style_ejecucion(v):
                if '(Control)' in str(v): return 'background-color: #003366; color: white'
                if '(Patio)' in str(v): return 'background-color: #1e88e5; color: white'
                if 'DOMINGO' in str(v): return 'background-color: #ff9900; color: white'
                if 'COMP' in str(v): return 'background-color: #ffd966'
                return ''

            st.write("### Malla Técnicos de Ejecución - Greenmovil")
            st.dataframe(m_f[cols].style.map(style_ejecucion), use_container_width=True)
            st.caption("Nota: Los huecos en Patio AM/PM durante fines de semana están diseñados para ser cubiertos por Operadores Senior.")
        else:
            st.error("No se pudo generar la malla. Verifica que el número de técnicos sea suficiente para cubrir 12 posiciones (6 en FDS).")
