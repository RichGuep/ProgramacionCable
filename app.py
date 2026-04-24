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

# --- 2. RUTA DEL LOGO (COINCIDENCIA EXACTA CON TU GITHUB) ---
# Cambiado de logo.png a MovilGo.png para que coincida con tu captura
LOGO_PATH = "MovilGo.png" 

# --- 3. ESTILOS CSS DE VANGUARDIA ---
st.markdown(f"""
    <style>
    .main {{ background-color: #f8fafc; }}
    
    /* Login Card */
    .login-card {{
        background-color: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        text-align: center;
        max-width: 450px;
        margin: auto;
    }}

    /* Banner Principal */
    .main-banner {{
        background: linear-gradient(135deg, #064e3b 0%, #10b981 100%);
        padding: 3.5rem;
        border-radius: 25px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }}

    /* Botones Modernos */
    .stButton>button {{
        width: 100%;
        border-radius: 12px;
        background-color: #10b981;
        color: white;
        font-weight: 700;
        border: none;
        padding: 0.8rem;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        background-color: #059669;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4);
    }}

    /* Estilo de las Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #f1f5f9;
        border-radius: 10px 10px 0 0;
        padding: 12px 24px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{ 
        background-color: #10b981 !important; 
        color: white !important; 
    }}
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNCIONES CORE ---
@st.cache_data
def load_base():
    try:
        # Intentamos cargar el archivo de empleados
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception:
        return None

def estilo_celdas(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fecaca'
    if 'T3' in v: return 'background-color: #1e293b; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0'
    if 'T2' in v: return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
    return 'color: #94a3b8; font-style: italic'

# --- 5. SISTEMA DE LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        # BUSCAR EL LOGO EN EL REPOSITORIO
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=280)
        else:
            st.markdown("<h1 style='color:#10b981;'>GREEN MÓVIL</h1>", unsafe_allow_html=True)
            
        st.markdown("<h2 style='color:#064e3b;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario Corporativo")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR AL PANEL"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 6. NAVEGACIÓN Y CARGA DE DATOS ---
df_raw = load_base()

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    menu = st.radio("MENÚ PRINCIPAL", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"])
    
    st.divider()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    mes_num = meses.index(mes_sel) + 1
    
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['auth'] = False
        st.rerun()

# --- 7. MÓDULO INICIO ---
if menu == "🏠 Inicio":
    st.markdown(f"""
        <div class="main-banner">
            <h1>Bienvenido Richard Guevara</h1>
            <p>Gestión Operativa MovilGo Pro | {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personal Activo", "145", "Registrados")
    c2.metric("Disponibilidad", "99.8%", "Óptimo")
    c3.metric("Novedades", "0", "Alertas")
    c4.metric("Estado Malla", "Sincronizado", "OK")

    st.markdown("### 🚀 Accesos Directos")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("#### 🏭 Planta Técnica")
            st.write("Generación de turnos T1-T2-T3 para Masters y Técnicos.")
    with col_b:
        with st.container(border=True):
            st.markdown("#### 👥 Auxiliares")
            st.write("Gestión de equipos 10/10 para atención al público.")

# --- 8. MÓDULO GESTIÓN DE MALLAS ---
elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("❌ Archivo 'empleados.xlsx' no encontrado.")
    else:
        tab1, tab2 = st.tabs(["🏭 Planta Operativa", "👥 Auxiliares 10/10"])
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        with tab1:
            st.subheader("Configuración Planta Técnica")
            c_config = st.columns(3)
            m_req = c_config[0].number_input("Masters", 1, 5, 2)
            ta_req = c_config[1].number_input("Técnicos A", 1, 15, 7)
            tb_req = c_config[2].number_input("Técnicos B", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cols_g = st.columns(4)
                for i in range(4):
                    with cols_g[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"t1_n_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"t1_d_{i}")
                        es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t1_t_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
                tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
                tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
                
                c_list = []
                for g_id, g_name in n_map.items():
                    for _ in range(m_req):
                        if not mas_p.empty: c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name}); mas_p = mas_p.iloc[1:]
                    for _ in range(ta_req):
                        if not tca_p.empty: c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name}); tca_p = tca_p.iloc[1:]
                    for _ in range(tb_req):
                        if not tcb_p.empty: c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name}); tcb_p = tcb_p.iloc[1:]
                
                df_celulas = pd.DataFrame(c_list)
                g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas = sorted(list(set([d["sem"] for d in d_info])))

                prob = LpProblem("MovilGo_Rota", LpMinimize)
                asig = LpVariable.dicts("Asig", (g_rotan, semanas, ["T1","T2","T3"]), cat='Binary')
                for s in semanas:
                    for t in ["T1","T2","T3"]: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
                    for g in g_rotan: prob += lpSum([asig[g][s][t] for t in ["T1","T2","T3"]]) == 1
                prob.solve(PULP_CBC_CMD(msg=0))
                res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in ["T1","T2","T3"] if value(asig[g][s][t]) == 1}

                final_rows = []
                g_disp_name = [g for g in n_map.values() if t_map[g] == "DISP"][0]

                for d_i in d_info:
                    desc_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                    hoy_labels = {}
                    for g in g_rotan:
                        if d_i["nom"] == d_map[g]: hoy_labels[g] = "DESC. LEY"
                        else: hoy_labels[g] = res_semanal.get((g, d_i["sem"]), "T1")
                    
                    label_disp = hoy_labels.get(desc_hoy[0], "T1") if desc_hoy else "T1"
                    
                    for g in n_map.values():
                        val = label_disp if g == g_disp_name else hoy_labels[g]
                        for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val})

                df_f = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                cols_sorted = sorted(df_f.columns, key=lambda x: int(x.split('-')[0]))
                st.dataframe(df_f[cols_sorted].style.map(estilo_celdas), use_container_width=True)

        with tab2:
            st.subheader("Malla Auxiliares (10/10)")
            df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy() if df_raw is not None else pd.DataFrame()
            if not df_ax.empty:
                with st.expander("Configurar Equipos", expanded=False):
                    ax_n_map, ax_d_map = {}, {}
                    c_ax = st.columns(5)
                    for i in range(5):
                        with c_ax[i]:
                            ne = st.text_input(f"Equipo {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                            de = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                            ax_n_map[i] = ne; ax_d_map[ne] = de

                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    df_ax['equipo'] = [ax_n_map[i % 5] for i in range(len(df_ax))]
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    
                    rows_ax = []
                    pool = ["T1", "T2", "T1", "T2", "DISPO"]
                    for d_i in d_info_ax:
                        shift = d_i["sem"] % 5
                        turnos_hoy = pool[-shift:] + pool[:-shift]
                        for idx, eq in enumerate(ax_n_map.values()):
                            t_f = "DESC. LEY" if d_i["nom"] == ax_d_map[eq] else turnos_hoy[idx]
                            for _, emp in df_ax[df_ax['equipo'] == eq].iterrows():
                                rows_ax.append({"Equipo": eq, "Empleado": emp['nombre'], "Label": d_i["label"], "Turno": t_f})

                    piv_ax = pd.DataFrame(rows_ax).pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                    cols_ax_sorted = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))
                    st.dataframe(piv_ax[cols_ax_sorted].style.map(estilo_celdas), use_container_width=True)

# --- 9. MÓDULO BASE DE DATOS ---
elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.dataframe(df_raw, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_raw.to_excel(writer, index=False)
        st.download_button("📥 Descargar Base de Datos", data=buffer.getvalue(), file_name="respaldo_base.xlsx")
