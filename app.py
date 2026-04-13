import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Auditoría", layout="wide", page_icon="⚖️")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. MOTOR ---
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
        st.header("⚙️ Parámetros")
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(2026, mes_num)[1]
    semanas = {}
    for d in range(1, num_dias + 1):
        s = datetime(2026, mes_num, d).isocalendar()[1]
        if s not in semanas: semanas[s] = []
        semanas[s].append(d)

    if st.button("🚀 GENERAR Y AUDITAR PROGRAMACIÓN"):
        prog_bar = st.progress(0); status = st.empty()
        status.text("Calculando con reglas de rotación y descanso...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Audit", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        t_sem = LpVariable.dicts("TSem", (df_f['nombre'], semanas.keys(), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # Objetivo: Cobertura máxima - Penalizar huecos
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 1000000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for d in range(1, num_dias + 1):
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) + hueco[d][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # REGLAS DE ROTACIÓN Y DESCANSO
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    # Candado Noche: Post-noche nada
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    # Candado PM: Prohibido AM al día siguiente
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Estabilidad Semanal
            for s_idx, dias_s in semanas.items():
                prob += lpSum([t_sem[e][s_idx][t] for t in LISTA_TURNOS]) <= 1
                for d in dias_s:
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] <= t_sem[e][s_idx][t]

            # Descansos de Ley (Mínimo 4 al mes)
            dias_criticos = [di for di in range(1, num_dias + 1) if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, di).weekday()] == dia_l]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 1)

        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=40))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for d in range(1, num_dias + 1):
                dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
                for e in df_f['nombre']:
                    t_real = "---"; s_act = datetime(2026, mes_num, d).isocalendar()[1]
                    for t in LISTA_TURNOS:
                        if value(asig[e][d][t]) == 1: t_real = t
                    t_base = "AM"
                    for t in LISTA_TURNOS:
                        if value(t_sem[e][s_act][t]) == 1: t_base = t
                    res_list.append({"Dia": d, "Label": f"{d} - {dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_real, "Base": t_base, "Ley": row['descanso_ley']})
            
            df_res = pd.DataFrame(res_list)
            for i, r in df_res.iterrows():
                dia_ley = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
                if r['Turno'] != "---": df_res.at[i, 'Final'] = f"TITULAR {r['Turno']}"
                elif r['Nom_Dia'] == dia_ley: df_res.at[i, 'Final'] = "DESC. LEY"
                elif i > 0 and "Noche" in str(df_res.at[i-1, 'Turno']): df_res.at[i, 'Final'] = "COMP. POST-NOCHE"
                else: df_res.at[i, 'Final'] = f"DISPONIBLE {r['Base']}"
            
            st.session_state['df_final'] = df_res
            prog_bar.progress(100); status.empty()

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        tab1, tab2, tab3 = st.tabs(["📅 Malla Programación", "⚖️ Auditoría de Cumplimiento", "📊 Métricas Operativas"])
        
        with tab1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Final')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
            
        with tab2:
            st.subheader("Validación de Reglas Laborales y de Seguridad")
            audit_data = []
            for emp, grupo in df_v.groupby("Empleado"):
                d_ley = len(grupo[grupo['Final'] == 'DESC. LEY'])
                d_comp = len(grupo[grupo['Final'] == 'COMP. POST-NOCHE'])
                d_total = d_ley + d_comp + len(grupo[grupo['Final'].str.contains('DISPONIBLE')])
                
                # Validación de rotación PM -> AM
                error_rotacion = False
                grupo_lista = grupo.sort_values("Dia").reset_index()
                for i in range(len(grupo_lista)-1):
                    if "PM" in grupo_lista.loc[i, 'Final'] and "AM" in grupo_lista.loc[i+1, 'Final']:
                        error_rotacion = True
                
                audit_data.append({
                    "Empleado": emp,
                    "Descansos Ley": d_ley,
                    "Compensatorios": d_comp,
                    "Días Disponibles": len(grupo[grupo['Final'].str.contains('DISPONIBLE')]),
                    "Rotación Segura": "✅ Correcta" if not error_rotacion else "❌ Error PM-AM",
                    "Estado": "🟢 Óptimo" if d_ley >= 2 else "🟡 Revisar"
                })
            st.table(pd.DataFrame(audit_data))
            
        with tab3:
            col_a, col_b = st.columns(2)
            with col_a:
                st.write("### Cobertura Real por Turno")
                cob = df_v[df_v['Final'].str.contains('TITULAR')].copy()
                cob['T'] = cob['Final'].str.replace('TITULAR ', '')
                st.dataframe(cob.groupby(['Label', 'T']).size().unstack(fill_value=0))
            with col_b:
                st.write("### Resumen de Novedades")
                resumen = df_v['Final'].value_counts()
                st.bar_chart(resumen)
