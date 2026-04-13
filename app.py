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
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 52px; border: none; }
    .stTabs [aria-selected="true"] { background-color: #1a365d !important; color: white !important; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        col1, col_login, col3 = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if os.path.exists("logo_movilgo.png"): 
                st.image("logo_movilgo.png", use_container_width=True)
            else: 
                st.markdown("<h1 style='text-align:center; color:#1a365d;'>MovilGo</h1>", unsafe_allow_html=True)
            
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True
                        st.session_state['user_name'] = "Richard Guevara"
                        st.rerun()
                    else: st.error("Credenciales Incorrectas")
            
            # Logos alineados (Logo 3 al centro)
            st.markdown("<div style='display:flex; justify-content:center; align-items:center; gap:40px; margin-top:30px;'>", unsafe_allow_html=True)
            for lp in ["logo_empresa_1.png", "logo_empresa_3.png", "logo_empresa_2.png"]:
                if os.path.exists(lp): st.image(lp, width=120)
            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

login_page()

# --- 4. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descanso")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descanso_ley'})
    except Exception as e:
        return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo Operativo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    if st.button("🚀 GENERAR MALLA ÓPTIMA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Final", LpMaximize)
        
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        cambio = LpVariable.dicts("Cambio", (df_f['nombre'], range(2, num_dias + 1)), cat='Binary')
        
        # Objetivo: Maximizar cobertura + Penalizar cambios (Estabilidad de turno)
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([cambio[e][d] * 2 for e in df_f['nombre'] for d in range(2, num_dias + 1)])

        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    # Bloqueo Salud: No turno tras Noche
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                    for t in LISTA_TURNOS:
                        prob += asig[e][d][t] - asig[e][d+1][t] <= cambio[e][d+1]

            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_l_nom]
            # Solo 2 días de ley trabajados (Cumplimiento 2+2)
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) == (len(dias_criticos) - 2)

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
                
                # Turno base para Disponibilidad
                t_mode = grupo[grupo['Turno'].isin(LISTA_TURNOS)]['Turno'].mode()
                t_base = t_mode[0] if not t_mode.empty else "AM"

                # 1. Marcar los 2 DESC. LEY obligatorios
                idx_fijos = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_ley_nom)].head(2).index
                grupo.loc[idx_fijos, 'Turno'] = 'DESC. LEY'
                
                # 2. Compensatorios SÓLO si trabajó su día de ley (Sáb o Dom)
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_ley_nom) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, row_f in findes_trab.iterrows():
                    # Prioridad: Si salió de noche, usar el día siguiente como compensatorio
                    check_post = grupo[(grupo['Dia'] == row_f['Dia'] + 1) & (grupo['Turno'] == '---')]
                    if not check_post.empty:
                        grupo.loc[check_post.index, 'Turno'] = 'DESC. COMPENSATORIO'
                    else:
                        hueco = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                        if not hueco.empty:
                            grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'
                
                # 3. Rellenar Disponibilidad con el turno base
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = f"DISPONIBLE {t_base}"
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            st.success("✅ Malla Generada")
        else:
            st.error("❌ Conflicto de reglas. Intenta bajar el cupo operativo.")

    # --- 5. RENDERIZADO DE TABLAS ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        def style_map(v):
            if 'LEY' in v: return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if 'COMPENSATORIO' in v: return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if 'DISPONIBLE' in v: return 'background-color: #e6f3ff; color: #004080'
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
                audit.append({"Empleado": e, "Ley": dia_l, "Trabajados": f_t, "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']), "Estado": "✅ Correcto" if (f_t + len(g[g['Turno'] == 'DESC. LEY']) == len(g[g['Nom_Dia'] == dia_l])) else "⚠️"})
            st.table(pd.DataFrame(audit))
