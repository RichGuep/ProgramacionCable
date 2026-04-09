import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")

# Definición global de turnos para acceso en todo el script
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS CORPORATIVOS (Century Gothic & UI Premium) ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');

    html, body, [class*="st-"], div, span, p, text {
        font-family: 'Century Gothic', sans-serif !important;
    }

    .stApp { background-color: #f8fafc; }

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
    }

    .logo-footer-container {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 50px;
        margin-top: 40px;
    }

    div.stButton > button {
        background-color: #2563eb;
        color: white;
        font-weight: bold;
        border-radius: 10px;
        height: 52px;
        border: none;
    }

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

            st.markdown("<div class='logo-footer-container'>", unsafe_allow_html=True)
            orden_logos = ["logo_empresa_1.png", "logo_empresa_3.png", "logo_empresa_2.png"]
            for lp in orden_logos:
                if os.path.exists(lp):
                    st.image(lp, width=130)
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.stop()

login_page()

# --- 4. PANEL DE CONTROL ---
st.sidebar.markdown(f"### 👤 Admin: {st.session_state['user_name']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state['auth'] = False
    st.rerun()

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descripcion")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descripcion'})
    except:
        return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)
        tipo_vista = st.radio("Visualización", ["Semanas", "Mes Completo"])

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = []
    dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        n_sem = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
        dias_info.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_sem, "label": f"{d} - {dias_esp[fecha.weekday()]}"})

    if st.button("🚀 GENERAR MALLA ÓPTIMA"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Core", LpMaximize)
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        
        # Objetivo: Maximizar cobertura
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e, desc = row['nombre'], row['descripcion']
            dia_c_nom = "Sab" if "sabado" in desc else "Dom"
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            f_c = [di["n"] for di in dias_info if di["nombre"] == dia_c_nom]
            prob += lpSum([asig[e][d][t] for d in f_c for t in LISTA_TURNOSfeatured]) == (len(f_c) - 2)
            # Días laborados moderados para permitir compensación (Meta 17-18 días)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= 17

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for di in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": di["n"], "Label": di["label"], "Semana": di["semana"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Contrato": df_f[df_f['nombre']==e]['descripcion'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
                
                # 1. Reservar Contractuales (2 por ley)
                idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
                grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
                
                # 2. Forzar Compensatorios L-V (Mandatorios)
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_c_nom) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, row_f in findes_trab.iterrows():
                    # Buscar espacio vacío '---' en la semana siguiente (7 días L-V)
                    ventana_comp = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & 
                                         (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))]
                    if not ventana_comp.empty:
                        grupo.loc[ventana_comp.head(1).index, 'Turno'] = 'DESC. L-V'
                
                # 3. Lo que sobre es DISPO
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            st.success("✅ Malla Generada con Compensatorios Legales")

    # --- 5. RENDERIZADO ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        df_v['ID_Full'] = df_v['Empleado'] + " (" + df_v['Contrato'].str.upper() + ")"
        
        def style_map(v):
            if v == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if v == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if v == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        t_malla, t_filtro, t_audit = st.tabs(["📅 Malla Operativa", "🔍 Filtro Empleado", "⚖️ Auditoría Legal"])

        with t_malla:
            if tipo_vista == "Mes Completo":
                m_f = df_v.pivot(index='ID_Full', columns='Label', values='Turno')
                st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_map), use_container_width=True)
            else:
                for s in sorted(df_v['Semana'].unique()):
                    st.write(f"#### Semana {s}")
                    m_s = df_v[df_v['Semana'] == s].pivot(index='ID_Full', columns='Label', values='Turno')
                    st.dataframe(m_s[sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_map), use_container_width=True)

        with t_filtro:
            noms = sorted(df_v['Empleado'].unique())
            sel = st.multiselect("Consultar Personal:", noms)
            if sel:
                m_i = df_v[df_v['Empleado'].isin(sel)].pivot(index='ID_Full', columns='Label', values='Turno')
                st.dataframe(m_i[sorted(m_i.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(style_map), use_container_width=True)

        with t_audit:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                d_c = "Sab" if "sabado" in g['Contrato'].iloc[0] else "Dom"
                f_t = len(g[(g['Nom_Dia'] == d_c) & (g['Turno'].isin(LISTA_TURNOS))])
                audit.append({
                    "Empleado": e, "Findes Trabajados": f_t, 
                    "Compensatorios L-V": len(g[g['Turno'] == 'DESC. L-V']), 
                    "Ley 1-1": "✅ Cumple" if len(g[g['Turno'] == 'DESC. L-V']) >= f_t else "⚠️ Pendiente"
                })
            st.table(pd.DataFrame(audit))
