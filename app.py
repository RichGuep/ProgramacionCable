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
    .logo-footer-container { display: flex; justify-content: center; align-items: center; gap: 50px; margin-top: 40px; }
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
            else: st.markdown("<h1 class='movilgo-title'>MovilGo</h1>", unsafe_allow_html=True)
            st.markdown("<div class='login-box'>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.session_state['user_name'] = "Richard Guevara"; st.rerun()
                    else: st.error("Credenciales Incorrectas")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<div class='logo-footer-container'>", unsafe_allow_html=True)
            for lp in ["logo_empresa_1.png", "logo_empresa_3.png", "logo_empresa_2.png"]:
                if os.path.exists(lp): st.image(lp, width=130)
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
        c_des = next((c for c in df.columns if 'des' in c), "descanso") # CAMBIO A COLUMNA DESCANSO
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "semana": (d + datetime(ano_sel, mes_num, 1).weekday() - 1) // 7 + 1, "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    if st.button("🚀 GENERAR MALLA ÓPTIMA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Final", LpMaximize)
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            # LEER DIRECTAMENTE DE LA COLUMNA DESCANSO
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias: # Higiene sueño
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            # GARANTÍA DE LEY: Máximo 2 trabajados de su día de descanso al mes
            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= 17

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for di in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": di["n"], "Label": di["label"], "Semana": di["semana"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Ley_Descanso": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_ley_nom = "Sab" if "sab" in str(grupo['Ley_Descanso'].iloc[0]).lower() else "Dom"
                
                # 1. Marcar descansos fijos (los que no trabajó)
                idx_fijos = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_ley_nom)].head(2).index
                grupo.loc[idx_fijos, 'Turno'] = 'DESC. LEY'
                
                # 2. Compensatorios obligatorios L-V si trabajó su día de ley
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_ley_nom) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, row_f in findes_trab.iterrows():
                    # Buscar el primer día libre (---) en los 7 días siguientes L-V
                    hueco = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                    if not hueco.empty:
                        grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'
                
                # 3. Disponibilidad
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            st.success("✅ Malla Generada respetando columna 'Descanso'")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_map(v):
            if v == 'DESC. LEY': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if v == 'DESC. COMPENSATORIO': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if v == 'DISPONIBILIDAD': return 'background-color: #e6f3ff; color: #004080'
            return ''

        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "🔍 Filtro Empleado", "⚖️ Auditoría Legal"])
        with t1:
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_map), use_container_width=True)
        with t3:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                dia_l = "Sab" if "sab" in str(g['Ley_Descanso'].iloc[0]).lower() else "Dom"
                f_t = len(g[(g['Nom_Dia'] == dia_l) & (g['Turno'].isin(LISTA_TURNOS))])
                audit.append({"Empleado": e, "Día Ley": dia_l, "Días Ley Trabajados": f_t, "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']), "Estado": "✅ Cumple" if len(g[g['Turno'] == 'DESC. COMPENSATORIO']) >= f_t else "⚠️ Pendiente"})
            st.table(pd.DataFrame(audit))
