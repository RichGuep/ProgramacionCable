import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Control Total", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border-top: 5px solid #1e293b; text-align: center; }
    .metric-val { font-size: 1.5rem; font-weight: bold; color: #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. MOTOR DE DATOS ---
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
        cupo_manual = st.number_input("Cupo por Turno", 1, 20, 2)
        peso_estabilidad = st.slider("Estabilidad (Evitar rotación diaria)", 10, 200, 100)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button(f"🚀 GENERAR MALLA 2+2: {cargo_sel}"):
        with st.status("Ejecutando motor con restricciones de estabilidad...", expanded=True) as status:
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            
            prob = LpProblem("Malla_MovilGo_Estable", LpMaximize)
            
            # Variables
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
            noche_sem = LpVariable.dicts("NocheSem", (nombres, semanas_mes), cat='Binary')

            # OBJETIVO: Priorizar estabilidad y cumplimiento de turnos
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                    lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

            # 1. Cupos por turno
            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                dl_val = str(row['descanso_ley']).lower()
                dia_ley = "Vie" if "vie" in dl_val else ("Sab" if "sab" in dl_val else "Dom")

                # 2. Máximo 1 turno al día
                for d in dias_range:
                    prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                    
                    # Lógica de MANTENER turno (Estabilidad)
                    if d > 1:
                        for t in LISTA_TURNOS:
                            prob += mantiene[e][d][t] <= asig[e][d][t]
                            prob += mantiene[e][d][t] <= asig[e][d-1][t]

                # 3. Restricción de ROTACIÓN (PM -> AM prohibido)
                for d in range(1, num_dias):
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

                # 4. Control de Noches Semanales
                for s in semanas_mes:
                    d_s = [di["n"] for di in dias_info if di["semana"] == s]
                    for d in d_s:
                        prob += noche_sem[e][s] >= asig[e][d]["Noche"]
                prob += lpSum([noche_sem[e][s] for s in semanas_mes]) <= 2

                # 5. Descansos de Ley (Mínimo 2 en su día de contrato)
                d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
                prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)

            st.write("🧠 Resolviendo... buscando estabilidad de bloques.")
            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=40, gapRel=0.05))

            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                res_list = []
                for di in dias_info:
                    for e in nombres:
                        t_asig = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[e][di["n"]][t]) == 1: t_asig = t
                        res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
                
                df_res = pd.DataFrame(res_list)
                lista_final = []
                for emp, grupo in df_res.groupby("Empleado"):
                    grupo = grupo.sort_values("Dia").copy()
                    l_val = str(grupo['Ley'].iloc[0]).lower()
                    d_ley = "Vie" if "vie" in l_val else ("Sab" if "sab" in l_val else "Dom")
                    
                    # --- POST-PROCESADO DE DESCANSOS ---
                    # A. Descanso de Ley
                    idx_l = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == d_ley)].head(2).index
                    grupo.loc[idx_l, 'Turno'] = 'DESC. LEY'
                    
                    # B. Descanso por rotación de NOCHE (Fijo)
                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] != 'Noche':
                            if grupo.iloc[i+1]['Turno'] == '---' or grupo.iloc[i+1]['Turno'] == 'DISPONIBILIDAD':
                                grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'

                    # C. Compensatorios
                    t_ley = grupo[(grupo['Nom_Dia'] == d_ley) & (grupo['Turno'].isin(LISTA_TURNOS))]
                    for _, r in t_ley.iterrows():
                        h = grupo[(grupo['Dia'] > r['Dia']) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1)
                        if not h.empty: grupo.loc[h.index, 'Turno'] = 'DESC. COMPENSATORIO'

                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                status.update(label="✅ Malla generada respetando estabilidad.", state="complete", expanded=False)
            else:
                st.error("Infactible. Sube el cupo o reduce la estabilidad.")

    # --- VISUALIZACIÓN ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
        cols_ord = sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))
        
        def color_t(v):
            if 'LEY' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
            if 'COMPENSATORIO' in v: return 'background-color: #fef9c3; color: #854d0e'
            if 'POST-NOCHE' in v: return 'background-color: #dcfce7; color: #166534; font-weight: bold'
            if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
            return ''

        st.dataframe(m_piv[cols_ord].style.map(color_t), use_container_width=True)
