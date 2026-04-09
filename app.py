import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")

# --- 2. ESTILOS PREMIUM (Century Gothic & UI Corporativa) ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');

    /* Fuente Global */
    html, body, [class*="st-"], div, span, p, text {
        font-family: 'Century Gothic', sans-serif !important;
    }

    /* Fondo App */
    .stApp { background-color: #f8fafc; }

    /* Login UI */
    .login-box {
        background-color: #ffffff;
        padding: 45px;
        border-radius: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
    
    h1.movilgo-title {
        color: #1a365d;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 5px;
        text-align: center;
        font-size: 3.2rem !important;
        margin-bottom: 2px;
    }

    /* Alineación de Logos en el pie del Login */
    .logo-footer-container {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 45px;
        margin-top: 40px;
    }

    .normalized-logo {
        max-height: 50px;
        width: auto;
        filter: grayscale(100%);
        opacity: 0.7;
        transition: 0.3s;
    }

    .normalized-logo:hover {
        filter: grayscale(0%);
        opacity: 1;
        transform: scale(1.05);
    }

    /* Botones */
    div.stButton > button {
        background-color: #2563eb;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        height: 52px;
        transition: 0.3s;
        border: none;
    }
    div.stButton > button:hover {
        background-color: #1d4ed8;
        transform: translateY(-2px);
    }

    /* Tabs */
    .stTabs [aria-selected="true"] {
        background-color: #1a365d !important;
        color: white !important;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. SISTEMA DE LOGIN ---
def login_page():
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False

    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # Logo Principal o Título
            if os.path.exists("logo_movilgo.png"):
                st.image("logo_movilgo.png", use_container_width=True)
            else:
                st.markdown("<h1 class='movilgo-title'>MovilGo</h1>", unsafe_allow_html=True)
            
            st.markdown("<p style='text-align: center; color: #64748b; letter-spacing: 1px;'>OPTIMIZACIÓN DE MALLAS Y CUMPLIMIENTO LEGAL</p>", unsafe_allow_html=True)

            with st.container():
                st.markdown("<div class='login-box'>", unsafe_allow_html=True)
                st.subheader("🔑 Acceso Administrador")
                with st.form("LoginForm"):
                    user = st.text_input("Correo Corporativo")
                    pwd = st.text_input("Contraseña", type="password")
                    if st.form_submit_button("INGRESAR AL SISTEMA"):
                        if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                            st.session_state['auth'] = True
                            st.session_state['user_name'] = "Richard Guevara"
                            st.rerun()
                        else:
                            st.error("Credenciales Incorrectas")
                st.markdown("</div>", unsafe_allow_html=True)

            # Logos del Grupo Empresarial abajo (Logo 3 al centro)
            st.markdown("<div class='logo-footer-container'>", unsafe_allow_html=True)
            # Orden: Empresa 1 | Empresa 3 (Centro) | Empresa 2
            orden = ["logo_empresa_1.png", "logo_empresa_3.png", "logo_empresa_2.png"]
            for logo_p in orden:
                if os.path.exists(logo_p):
                    st.markdown(f"<img src='app/{logo_p}' class='normalized-logo'>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.stop()

login_page()

# --- 4. PANEL PRINCIPAL (POST-LOGIN) ---
st.sidebar.markdown(f"### 👤 Admin: {st.session_state['user_name']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state['auth'] = False
    st.rerun()

# --- CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descripcion")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descripcion'})
        return df
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
        meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
        mes_num = meses_n.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)
        tipo_vista = st.radio("Visualización", ["Vista por Semanas", "Mes Completo"])

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = []
    dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        n_sem = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
        dias_info.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_sem, "label": f"{d} - {dias_esp[fecha.weekday()]}"})

    # --- MOTOR DE OPTIMIZACIÓN ---
    if st.button("🚀 GENERAR PROGRAMACIÓN ÓPTIMA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        turnos = ["AM", "PM", "Noche"]
        prob = LpProblem("MovilGo_Core", LpMaximize)
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), turnos), cat='Binary')
        mantiene = LpVariable.dicts("Mantiene", (df_f['nombre'], range(2, num_dias + 1), turnos), cat='Binary')

        # Objetivo: Cobertura + Estabilidad de Turno
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in turnos]) + \
                lpSum([mantiene[e][d][t] * 0.5 for e in df_f['nombre'] for d in range(2, num_dias + 1) for t in turnos])

        # Restricciones de cupo
        for di in dias_info:
            for t in turnos:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e, desc = row['nombre'], row['descripcion']
            dia_c = "Sab" if "sabado" in desc else "Dom"
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
                if d < num_dias: # Protección sueño y estabilidad
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                    for t in turnos:
                        prob += mantiene[e][d+1][t] <= asig[e][d][t]
                        prob += mantiene[e][d+1][t] <= asig[e][d+1][t]
            
            # Descansos legales de contrato (2 al mes)
            f_c = [di["n"] for di in dias_info if di["nombre"] == dia_c]
            prob += lpSum([asig[e][d][t] for d in f_c for t in turnos]) == (len(f_c) - 2)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 18

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for di in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in turnos:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({
                        "Dia": di["n"], "Label": di["label"], "Semana": di["semana"], 
                        "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, 
                        "Contrato": df_f[df_f['nombre']==e]['descripcion'].values[0]
                    })
            
            # Post-procesamiento de Compensatorios (Semana Siguiente)
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                d_c_n = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
                # Contractuales
                idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == d_c_n)].head(2).index
                grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
                # Compensatorios L-V vinculados
                f_trab = grupo[(grupo['Nom_Dia'] == d_c_n) & (grupo['Turno'].isin(turnos))]
                for _, row_f in f_trab.iterrows():
                    idx_comp = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & 
                                     (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].index
                    if not idx_comp.empty: grupo.loc[idx_comp[0], 'Turno'] = 'DESC. L-V'
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            st.success("Cálculo Finalizado")

    # --- VISUALIZACIÓN ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        df_v['ID_Full'] = df_v['Empleado'] + " (" + df_v['Contrato'].str.upper() + ")"
        
        def style_map(v):
            if v == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if v == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if v == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "🔍 Filtro por Empleado", "⚖️ Auditoría Legal"])

        with t1:
            if tipo_vista == "Mes Completo":
                m_f = df_v.pivot(index='ID_Full', columns='Label', values='Turno')
                cols = sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))
                st.dataframe(m_f[cols].style.map(style_map), use_container_width=True)
            else:
                for s in sorted(df_v['Semana'].unique()):
                    st.write(f"#### Semana {s}")
                    m_s = df_v[df_v['Semana'] == s].pivot(index='ID_Full', columns='Label', values='Turno')
                    cols_s = sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))
                    st.dataframe(m_s[cols_s].style.map(style_map), use_container_width=True)

        with t2:
            sel = st.multiselect("Seleccionar Personal:", sorted(df_v['Empleado'].unique()))
            if sel:
                m_i = df_v[df_v['Empleado'].isin(sel)].pivot(index='ID_Full', columns='Label', values='Turno')
                cols_i = sorted(m_i.columns, key=lambda x: int(x.split(' - ')[0]))
                st.dataframe(m_i[cols_i].style.map(style_map), use_container_width=True)

        with t3:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                d_c = "Sab" if "sabado" in g['Contrato'].iloc[0] else "Dom"
                f_trab = len(g[(g['Nom_Dia'] == d_c) & (g['Turno'].isin(turnos))])
                audit.append({
                    "Empleado": e, "Findes Trabajados": f_trab, 
                    "Compensatorios L-V": len(g[g['Turno'] == 'DESC. L-V']), 
                    "Ley 1-1": "✅ Cumple" if len(g[g['Turno'] == 'DESC. L-V']) >= f_trab else "⚠️ Revisar"
                })
            st.table(pd.DataFrame(audit))
