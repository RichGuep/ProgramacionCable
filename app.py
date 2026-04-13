import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")
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

# --- LOGIN (Simplificado para brevedad) ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    st.title("MovilGo - Ingreso")
    user = st.text_input("Usuario")
    pwd = st.text_input("Clave", type="password")
    if st.button("INGRESAR"):
        if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
            st.session_state['auth'] = True; st.rerun()
    st.stop()

# --- 4. MOTOR DE OPTIMIZACIÓN ---
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
        cupo_manual = st.number_input("Cupo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    if st.button("🚀 GENERAR PROGRAMACIÓN ÓPTIMA"):
        prog = st.progress(0); status = st.empty()
        status.text("Calculando con límite estricto de descansos...")
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Eficiencia", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        cambio = LpVariable.dicts("Cambio", (df_f['nombre'], range(2, num_dias + 1)), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # OBJETIVO: Cobertura máxima - Penalizar cambios de turno (estabilidad)
        prob += lpSum([asig[e][d][t] * 10 for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([cambio[e][d] * 50 for e in df_f['nombre'] for d in range(2, num_dias + 1)]) - \
                lpSum([hueco[d][t] * 1000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        # Restricción de Cupo
        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) + hueco[di["n"]][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # --- REGLA CRÍTICA: Máximo 4 o 5 días de descanso al mes ---
            # (Un descanso por semana para evitar exceso de días libres)
            max_descansos = 5 if num_dias > 28 else 4
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= (num_dias - max_descansos)

            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] - asig[e][d+1][t] <= cambio[e][d+1]

            # Ley 2+2: Descansa 2 fines de semana al mes
            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_l_nom]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) == (len(dias_criticos) - 2)

        prog.progress(50)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for di in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Ley_Descanso": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").reset_index(drop=True)
                dia_l_contrato = "Sab" if "sab" in str(grupo.loc[0, 'Ley_Descanso']).lower() else "Dom"
                
                # Identificar semanas donde NO descansó el fin de semana para dar compensatorio
                fines_trabajados = grupo[(grupo['Nom_Dia'] == dia_l_contrato) & (grupo['Turno'].isin(LISTA_TURNOS))]['Dia'].tolist()

                for i in range(len(grupo)):
                    if grupo.loc[i, 'Turno'] == '---':
                        if grupo.loc[i, 'Nom_Dia'] == dia_l_contrato:
                            grupo.loc[i, 'Turno'] = 'DESC. LEY'
                        elif i > 0 and grupo.loc[i-1, 'Turno'] == 'Noche':
                            # Compensatorio SOLO si trabajó el fin de semana previo
                            if any(grupo.loc[i, 'Dia'] > f and grupo.loc[i, 'Dia'] <= f+7 for f in fines_trabajados):
                                grupo.loc[i, 'Turno'] = 'DESC. COMPENSATORIO'
                            else:
                                grupo.loc[i, 'Turno'] = 'DISPONIBLE'
                        else:
                            grupo.loc[i, 'Turno'] = 'DISPONIBLE'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final)
            prog.progress(100); status.empty(); time.sleep(1); prog.empty()
        else:
            st.error("No se pudo optimizar con estas restricciones.")

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Turno')
        st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
