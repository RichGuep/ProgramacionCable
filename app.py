import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo Pro | Green Móvil",
    layout="wide",
    page_icon="🚌"
)

# ID DE TU LOGO (Extraído de tu link)
LOGO_URL = "https://drive.google.com/uc?id=16oqiPZoHcGcfmJIuOntRyFywnHF48sd1"

# --- 2. ESTILOS CSS PERSONALIZADOS (Vanguardia) ---
st.markdown(f"""
    <style>
    /* Fondo general */
    .main {{ background-color: #f8fafc; }}
    
    /* Login Box mejorado */
    .login-container {{
        background-color: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        text-align: center;
    }}

    /* Botones con estilo Green Movil */
    .stButton>button {{
        width: 100%;
        border-radius: 10px;
        background-color: #10b981;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.7rem;
        transition: all 0.3s ease;
    }}
    .stButton>button:hover {{
        background-color: #059669;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }}

    /* Banner Principal */
    .main-banner {{
        background: linear-gradient(135deg, #064e3b 0%, #10b981 100%);
        padding: 3rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }}

    /* Estilo para las métricas */
    [data-testid="stMetricValue"] {{ 
        color: #064e3b !important; 
        font-weight: bold !important;
    }}
    
    /* Tabs personalizados */
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #e2e8f0;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        color: #475569;
    }}
    .stTabs [aria-selected="true"] {{ 
        background-color: #10b981 !important; 
        color: white !important; 
    }}
    </style>
""", unsafe_allow_html=True)

# --- 3. FUNCIONES DE APOYO ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception:
        return None

def estilo_malla(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fecaca'
    if 'T3' in v: return 'background-color: #1e293b; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0'
    if 'T2' in v: return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
    return 'color: #94a3b8; font-style: italic'

# --- 4. SISTEMA DE LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.image(LOGO_URL, width=250)
        st.markdown("<h2 style='color:#064e3b; margin-top:10px;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#64748b;'>Control de Operaciones Green Móvil</p>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INICIAR SESIÓN"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. NAVEGACIÓN Y SIDEBAR ---
df_raw = load_base()

with st.sidebar:
    st.image(LOGO_URL, use_container_width=True)
    st.markdown("<hr style='margin:10px 0;'>", unsafe_allow_html=True)
    menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"], label_visibility="collapsed")
    
    st.divider()
    st.subheader("🗓️ Periodo de Gestión")
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    mes_num = meses.index(mes_sel) + 1

    if st.button("🚪 Salir"):
        st.session_state['auth'] = False
        st.rerun()

# --- 6. MÓDULOS DE LA APP ---

# --- MÓDULO INICIO ---
if menu == "🏠 Inicio":
    st.markdown(f"""
        <div class="main-banner">
            <h1 style='font-size: 3rem;'>Bienvenido, Richard Guevara</h1>
            <p style='font-size: 1.2rem;'>Gestión Integral de Personal y Turnos Operativos - {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)

    # Métricas clave
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        with st.container(border=True):
            st.metric("Total Planta", "145 Pers.", "+2% vs dic")
    with c2:
        with st.container(border=True):
            st.metric("Disponibilidad", "99.1%", "Óptimo")
    with c3:
        with st.container(border=True):
            st.metric("Turnos Hoy", "48", "En curso")
    with c4:
        with st.container(border=True):
            st.metric("Novedades", "0", "Sin alertas")

    st.markdown("### ⚡ Accesos Directos")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("#### 🔧 Planta Técnica (T1-T2-T3)")
            st.write("Generación de malla automatizada para Masters y Técnicos mediante optimización lineal.")
            if st.button("Ir a Malla Técnica"): 
                st.info("Selecciona 'Gestión de Mallas' en el menú lateral.")
    with col_b:
        with st.container(border=True):
            st.markdown("#### 👥 Auxiliares de Abordaje")
            st.write("Configuración de rotación 10/10 para el personal de atención al público y abordaje.")
            if st.button("Ir a Malla Auxiliares"):
                st.info("Selecciona 'Gestión de Mallas' en el menú lateral.")

# --- MÓDULO GESTIÓN DE MALLAS ---
elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("❌ No se encontró el archivo 'empleados.xlsx'. Por favor cárguelo en la carpeta del script.")
    else:
        tab1, tab2 = st.tabs(["🔧 Planta Técnica (Operativa)", "👥 Auxiliares (10/10)"])
        
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        with tab1:
            st.markdown("### Configuración de Planta Técnica")
            cols_req = st.columns(3)
            m_req = cols_req[0].number_input("Masters x Grupo", 1, 5, 2)
            ta_req = cols_req[1].number_input("Técnicos A x Grupo", 1, 15, 7)
            tb_req = cols_req[2].number_input("Técnicos B x Grupo", 1, 10, 3)

            with st.expander("📝 Definición de Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                c_g = st.columns(4)
                for i in range(4):
                    with c_g[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"t1_n_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"t1_d_{i}")
                        es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t1_t_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA DE TÉCNICOS"):
                # Lógica de distribución
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

                # Optimización con PuLP
                prob = LpProblem("MovilGo_Rota", LpMinimize)
                asig = LpVariable.dicts("Asig", (g_rotan, semanas, ["T1","T2","T3"]), cat='Binary')
                for s in semanas:
                    for t in ["T1","T2","T3"]: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
                    for g in g_rotan: prob += lpSum([asig[g][s][t] for t in ["T1","T2","T3"]]) == 1
                prob.solve(PULP_CBC_CMD(msg=0))
                res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in ["T1","T2","T3"] if value(asig[g][s][t]) == 1}

                final_rows = []
                g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]
                ultimo_t_disp = "T1"

                for d_i in d_info:
                    desc_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                    hoy_vals = {}
                    for g in g_rotan:
                        if d_i["nom"] == d_map[g]: hoy_vals[g] = "DESC. LEY"
                        else: hoy_vals[g] = res_semanal.get((g, d_i["sem"]), "T1")
                    
                    # Regla Disponibilidad
                    if d_i["nom"] == d_map[g_disp]: label_disp = "DESC. LEY"
                    else:
                        label_disp = hoy_vals.get(desc_hoy[0], "T1") if desc_hoy else "T1"
                    
                    for g in n_map.values():
                        val_f = label_disp if g == g_disp else hoy_vals[g]
                        for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val_f})

                df_piv = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                st.success(f"Malla generada para {mes_sel}")
                st.dataframe(df_piv.style.map(estilo_malla), use_container_width=True)

        with tab2:
            st.markdown("### Configuración de Auxiliares")
            df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
            
            if df_ax.empty:
                st.warning("⚠️ No se encontraron empleados con el cargo de 'Auxiliar'.")
            else:
                with st.expander("👥 Definir Equipos de Trabajo", expanded=False):
                    ax_n_map, ax_d_map = {}, {}
                    c_ax = st.columns(5)
                    for i in range(5):
                        with c_ax[i]:
                            ne = st.text_input(f"Equipo {i+1}", f"EQUIPO {chr(65+i)}", key=f"ax_n_{i}")
                            de = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                            ax_n_map[i] = ne; ax_d_map[ne] = de

                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    # Asignar equipo por rotación simple
                    df_ax = df_ax.reset_index(drop=True)
                    df_ax['equipo'] = [ax_n_map[i % 5] for i in range(len(df_ax))]
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    
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
                    st.dataframe(piv_ax.style.map(estilo_malla), use_container_width=True)

# --- MÓDULO BASE DE DATOS ---
elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.info("Vista previa de los empleados registrados en el sistema.")
        st.dataframe(df_raw, use_container_width=True)
        
        st.markdown("### Acciones de Datos")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                label="📥 Descargar Base Actual (Excel)",
                data=open("empleados.xlsx", "rb"),
                file_name=f"Base_Empleados_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with c2:
            st.warning("Para actualizar el personal, reemplace el archivo 'empleados.xlsx' en el servidor.")
    else:
        st.error("No se pudo leer la base de datos.")
