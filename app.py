import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo Pro | Green Móvil",
    layout="wide",
    page_icon="🚌"
)

# --- 2. RUTA DEL LOGO (GitHub) ---
LOGO_PATH = "MovilGo.png" 

# --- 3. ESTILOS CSS PROFESIONALES ---
st.markdown(f"""
    <style>
    /* Limpieza de interfaz de Streamlit */
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
        display: none !important;
    }}

    .main {{ background-color: #f8fafc; }}
    
    /* Login Card Centrada */
    .login-card {{
        background-color: white;
        padding: 3.5rem;
        border-radius: 24px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
        border: 1px solid #e2e8f0;
        text-align: center;
        max-width: 500px;
        margin: 100px auto;
    }}

    /* Logo y Texto */
    div[data-testid="stImage"] > img {{
        display: block;
        margin-left: auto;
        margin-right: auto;
    }}

    .brand-title {{
        color: #064e3b;
        font-size: 2.6rem;
        font-weight: 850;
        margin-top: 20px;
        text-align: center;
        letter-spacing: -1px;
    }}

    .brand-subtitle {{
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 30px;
        text-align: center;
    }}

    /* Botón Green Movil */
    .stButton>button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 700;
        height: 3.5rem;
        border: none;
        transition: 0.3s;
    }}
    .stButton>button:hover {{
        box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4);
        transform: translateY(-2px);
    }}
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNCIONES CORE ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except:
        return None

def estilo_malla(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fecaca'
    if 'T3' in v: return 'background-color: #1e293b; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0'
    if 'T2' in v: return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
    return 'color: #94a3b8; font-style: italic'

# --- 5. LÓGICA DE LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=320)
        st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle">Planificador de Turnos Green Móvil</div>', unsafe_allow_html=True)
        
        with st.form("Login"):
            u = st.text_input("Usuario Corporativo")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR AL PANEL"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Acceso denegado")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 6. PANEL PRINCIPAL ---
df_raw = load_base()

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"], label_visibility="collapsed")
    st.divider()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    mes_num = meses.index(mes_sel) + 1
    if st.button("Cerrar Sesión"):
        st.session_state['auth'] = False
        st.rerun()

# --- MÓDULO INICIO ---
if menu == "🏠 Inicio":
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
            <h1>Bienvenido Richard Guevara</h1>
            <p>Control Operativo de Planta y Personal - {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Personal Técnico", "Planta Completa", "Activo")
    col2.metric("Auxiliares", "10/10", "Programados")
    col3.metric("Sincronización", "Sistemas OK", "Hoy")

# --- MÓDULO MALLAS ---
elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("Error: No se encontró el archivo 'empleados.xlsx'")
    else:
        tab1, tab2 = st.tabs(["Planta Operativa (T1-T3)", "Auxiliares de Abordaje"])
        DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

        with tab1:
            st.subheader("Configuración de Planta Técnica")
            c_req = st.columns(3)
            m_req = c_req[0].number_input("Masters x Grupo", 1, 5, 2)
            ta_req = c_req[1].number_input("Tec A x Grupo", 1, 15, 7)
            tb_req = c_req[2].number_input("Tec B x Grupo", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cg = st.columns(4)
                for i in range(4):
                    with cg[i]:
                        gn = st.text_input(f"Grupo {i+1}", f"G{i+1}", key=f"gn_{i}")
                        ds = st.selectbox(f"Descanso", DIAS, index=i%7, key=f"gd_{i}")
                        es_d = st.checkbox("Disponibilidad", value=(i==3), key=f"gt_{i}")
                        n_map[f"G{i+1}"] = gn; d_map[gn] = ds; t_map[gn] = "DISP" if es_d else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                # Filtro de personal por cargo
                mas = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
                tca = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
                tcb = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
                
                c_list = []
                for gn in n_map.values():
                    for _ in range(m_req):
                        if not mas.empty: c_list.append({**mas.iloc[0].to_dict(), "grupo": gn}); mas = mas.iloc[1:]
                    for _ in range(ta_req):
                        if not tca.empty: c_list.append({**tca.iloc[0].to_dict(), "grupo": gn}); tca = tca.iloc[1:]
                    for _ in range(tb_req):
                        if not tcb.empty: c_list.append({**tcb.iloc[0].to_dict(), "grupo": gn}); tcb = tcb.iloc[1:]
                
                df_cel = pd.DataFrame(c_list)
                g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info = [{"n": d, "nom": DIAS[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas = sorted(list(set([d["sem"] for d in d_info])))

                # Optimización PuLP
                prob = LpProblem("Malla", LpMinimize)
                asig = LpVariable.dicts("Asig", (g_rotan, semanas, ["T1","T2","T3"]), cat='Binary')
                for s in semanas:
                    for t in ["T1","T2","T3"]: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
                    for g in g_rotan: prob += lpSum([asig[g][s][t] for t in ["T1","T2","T3"]]) == 1
                prob.solve(PULP_CBC_CMD(msg=0))
                res_sem = {(g, s): t for g in g_rotan for s in semanas for t in ["T1","T2","T3"] if value(asig[g][s][t]) == 1}

                # Construcción de la matriz diaria
                final_rows = []
                g_disp_name = [g for g in n_map.values() if t_map[g] == "DISP"][0]
                
                for d_i in d_info:
                    desc_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                    hoy_vals = {g: ("DESC. LEY" if d_i["nom"] == d_map[g] else res_sem.get((g, d_i["sem"]), "T1")) for g in g_rotan}
                    
                    # Cobertura de Disponibilidad
                    label_disp = hoy_vals.get(desc_hoy[0], "T1") if desc_hoy else "T1"
                    
                    for g in n_map.values():
                        val = label_disp if g == g_disp_name else hoy_vals.get(g, "T1")
                        for _, m in df_cel[df_cel['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val})
                
                df_piv = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                cols_ord = sorted(df_piv.columns, key=lambda x: int(x.split('-')[0]))
                st.dataframe(df_piv[cols_ord].style.applymap(estilo_malla), use_container_width=True)

        with tab2:
            st.subheader("Malla Auxiliares (Rotación 10/10)")
            df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
            if not df_ax.empty:
                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"nom": DIAS[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    rows_ax = []
                    for d_i in d_info_ax:
                        for _, emp in df_ax.iterrows():
                            # Rotación simplificada por semana para auxiliares
                            t_ax = "T1" if d_i["sem"] % 2 == 0 else "T2"
                            t_f = "DESC. LEY" if d_i["nom"] == "Domingo" else t_ax
                            rows_ax.append({"Empleado": emp['nombre'], "Label": d_i["label"], "Turno": t_f})
                    piv_ax = pd.DataFrame(rows_ax).pivot(index='Empleado', columns='Label', values='Turno')
                    cols_ax = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))
                    st.dataframe(piv_ax[cols_ax].style.applymap(estilo_malla), use_container_width=True)

elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.dataframe(df_raw, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_raw.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="respaldo_base.xlsx")
