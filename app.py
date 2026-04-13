import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

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
    .stTabs [aria-selected="true"] { background-color: #1a365d !important; color: white !important; border-radius: 5px; }
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
            else: st.markdown("<h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.session_state['user_name'] = "Richard Guevara"; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. MOTOR ---
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
        cupo_manual = st.number_input("Cupo Operativo por Turno", 1, 10, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    if st.button("🚀 GENERAR MALLA SEGURA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Security", LpMaximize)
        
        # Variables: asig[empleado][dia][turno]
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        # Variable auxiliar para estabilidad (evitar cambios de turno)
        cambio = LpVariable.dicts("Cambio", (df_f['nombre'], range(2, num_dias + 1)), cat='Binary')
        
        # OBJETIVO: Maximizar cobertura pero penalizar FUERTEMENTE los cambios de turno (favorece bloques de 15 días)
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([cambio[e][d] * 2 for e in df_f['nombre'] for d in range(2, num_dias + 1)])

        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                
                # REGLA DE ORO: SI HACE NOCHE, EL DÍA SIGUIENTE QUEDA BLOQUEADO (DESCANSANDO)
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1 # Evita tarde-mañana
                    
                    # Lógica de Cambio de Turno para la función objetivo
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] - asig[e][d+1][t] <= cambio[e][d+1]

            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= 16

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
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
                grupo = grupo.sort_values("Dia").copy()
                dia_ley_nom = "Sab" if "sab" in str(grupo['Ley_Descanso'].iloc[0]).lower() else "Dom"
                
                # Turno base para disponibilidad
                t_mode = grupo[grupo['Turno'].isin(LISTA_TURNOS)]['Turno'].mode()
                t_base = t_mode[0] if not t_mode.empty else "AM"

                # 1. Asignar Descansos de Ley tras Noches (Estrategia de optimización)
                for i in range(len(grupo)-1):
                    if grupo.iloc[i]['Turno'] == "Noche" and grupo.iloc[i+1]['Nom_Dia'] == dia_ley_nom:
                        if len(grupo[grupo['Turno'] == 'DESC. LEY']) < 2:
                            grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. LEY'

                # 2. Completar los 2 Descansos de Ley si faltan
                while len(grupo[grupo['Turno'] == 'DESC. LEY']) < 2:
                    idx = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_ley_nom)].head(1).index
                    if not idx.empty: grupo.loc[idx, 'Turno'] = 'DESC. LEY'
                    else: break

                # 3. Asignar Compensatorios tras Noche o por trabajar día Ley
                for i in range(len(grupo)-1):
                    if grupo.iloc[i]['Turno'] == "Noche" and grupo.iloc[i+1]['Turno'] == "---":
                        grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. COMPENSATORIO'

                # Compensatorios por trabajar día contractual
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_ley_nom) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, row_f in findes_trab.iterrows():
                    ya_tiene = len(grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & (grupo['Turno'].str.contains("DESC"))])
                    if ya_tiene == 0:
                        hueco = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                        if not hueco.empty: grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'
                
                # 4. DISPONIBILIDAD (Solo donde el día NO es descanso y NO viene de noche)
                for i in range(len(grupo)):
                    if grupo.iloc[i]['Turno'] == '---':
                        if i > 0 and grupo.iloc[i-1]['Turno'] in ["Noche", "DISPONIBLE Noche"]:
                            # Esta parte técnicamente ya está cubierta por el motor, pero por seguridad:
                            grupo.iloc[i, grupo.columns.get_loc('Turno')] = 'DESC. COMPENSATORIO'
                        else:
                            grupo.iloc[i, grupo.columns.get_loc('Turno')] = f"DISPONIBLE {t_base}"
                
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            st.success("✅ Malla Generada: Seguridad Post-Noche y Estabilidad Semanal garantizada.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_map(v):
            if 'LEY' in v: return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if 'COMPENSATORIO' in v: return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if 'DISPONIBLE' in v: return 'background-color: #e6f3ff; color: #004080'
            if '---' in v: return 'background-color: white;'
            return 'background-color: #ccf5ff; color: #005580;'

        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "🔍 Filtro Empleado", "⚖️ Auditoría Legal"])
        with t1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_map), use_container_width=True)
        with t3:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                dia_l = "Sab" if "sab" in str(g['Ley_Descanso'].iloc[0]).lower() else "Dom"
                f_t = len(g[(g['Nom_Dia'] == dia_l) & (g['Turno'].isin(LISTA_TURNOS))])
                # Auditoría de Noches Seguidas
                noches_peligrosas = 0
                for i in range(len(g)-1):
                    if g.iloc[i]['Turno'] == "Noche" and g.iloc[i+1]['Turno'] in LISTA_TURNOS:
                        noches_peligrosas += 1
                
                audit.append({
                    "Empleado": e, 
                    "Día Ley": dia_l, 
                    "Trabajados": f_t, 
                    "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']), 
                    "Saltos Noche-Día": "❌ ERROR" if noches_peligrosas > 0 else "✅ SEGURO"
                })
            st.table(pd.DataFrame(audit))
