import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Control Legal", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border-top: 5px solid #1e293b; text-align: center; }
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
        st.header("⚙️ Parámetros")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 20, 2)
        peso_estabilidad = st.slider("Rigidez de Turno (Bloques)", 50, 300, 150)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button(f"🚀 GENERAR MALLA LEGAL: {cargo_sel}"):
        with st.status("Optimizando turnos y descansos...", expanded=True) as status:
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            
            prob = LpProblem("MovilGo_Final", LpMaximize)
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
            
            # Objetivo: Maximizar cobertura y estabilidad de bloques semanales
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                    lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                dl_val = str(row['descanso_ley']).lower()
                dia_ley = "Vie" if "vie" in dl_val else ("Sab" if "sab" in dl_val else "Dom")

                for d in dias_range:
                    prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                    if d > 1:
                        for t in LISTA_TURNOS:
                            prob += mantiene[e][d][t] <= asig[e][d][t]
                            prob += mantiene[e][d][t] <= asig[e][d-1][t]
                    
                    # Restricción de rotación prohibida (Hacia atrás)
                    if d < num_dias:
                        prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

                # Mínimo 2 descansos en su día contractual
                d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
                prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)

            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45, gapRel=0.05))

            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                res_list = []
                for di in dias_info:
                    for e in nombres:
                        t_asig = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[e][di["n"]][t]) == 1: t_asig = t
                        res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Semana": di["semana"], "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
                
                df_res = pd.DataFrame(res_list)
                lista_final = []
                
                for emp, grupo in df_res.groupby("Empleado"):
                    grupo = grupo.sort_values("Dia").copy()
                    lv = str(grupo['Ley'].iloc[0]).lower()
                    dl = "Vie" if "vie" in lv else ("Sab" if "sab" in lv else "Dom")
                    
                    # 1. Identificar Semanas trabajadas en día de ley para Compensatorios
                    semanas_a_compensar = []
                    for sem in semanas_mes:
                        dia_l_sem = grupo[(grupo['Semana'] == sem) & (grupo['Nom_Dia'] == dl)]
                        if not dia_l_sem.empty and dia_l_sem['Turno'].iloc[0] in LISTA_TURNOS:
                            semanas_a_compensar.append(sem)

                    # 2. Asignar 2 DESC. LEY fijos
                    idx_l = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dl)].head(2).index
                    grupo.loc[idx_l, 'Turno'] = 'DESC. LEY'

                    # 3. Asignar COMPENSATORIOS (Uno por semana, no juntos, inmediatamente semana siguiente)
                    for sem_trabajada in semanas_a_compensar:
                        # Buscar hueco en la semana siguiente (sem_trabajada + 1)
                        idx_comp = grupo[(grupo['Semana'] == sem_trabajada + 1) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1).index
                        if not idx_comp.empty:
                            grupo.loc[idx_comp, 'Turno'] = 'DESC. COMPENSATORIO'

                    # 4. Ajuste POST-NOCHE (Si el día siguiente a noche es libre, se etiqueta como ley/comp)
                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] != 'Noche':
                            # Si el siguiente es un descanso ya asignado o un hueco
                            if 'DESC' in str(grupo.iloc[i+1]['Turno']) or grupo.iloc[i+1]['Turno'] == '---':
                                actual = grupo.iloc[i+1]['Turno']
                                etiqueta = f"POST-NOCHE ({actual})" if actual != '---' else "DESC. POST-NOCHE"
                                grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = etiqueta

                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                status.update(label="✅ Malla generada con éxito.", state="complete", expanded=False)

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
        cols_ord = sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))
        
        def style_v(v):
            if 'LEY' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
            if 'COMPENSATORIO' in v: return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
            if 'POST-NOCHE' in v: return 'background-color: #dcfce7; color: #166534; font-weight: bold'
            if v == 'Noche': return 'background-color: #1e293b; color: white'
            return ''

        st.dataframe(m_piv[cols_ord].style.map(style_v), use_container_width=True)
