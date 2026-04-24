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

# --- 2. ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    /* Fondo y tipografía */
    .main { background-color: #f4f7f6; }
    
    /* Login Card */
    .login-container {
        background-color: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
    }

    /* Botones Modernos */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        background-color: #10b981;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.6rem;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #059669;
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    /* Headers y Banners */
    .main-banner {
        background: linear-gradient(135deg, #064e3b 0%, #10b981 100%);
        padding: 3rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }

    /* Tarjetas de Métricas */
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; color: #064e3b; }
    </style>
""", unsafe_allow_html=True)

# --- 3. LÓGICA DE DATOS ---
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

# --- 4. CONTROL DE ACCESO ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.2, 1])
    with col_login:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center; color:#064e3b;'>MovilGo Admin</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#6b7280;'>Ingrese sus credenciales de Richard Guevara</p>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("ACCEDER AL PANEL"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Credenciales no válidas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 5. DASHBOARD PRINCIPAL ---
df_raw = load_base()

with st.sidebar:
    st.markdown("<h2 style='color:#10b981;'>MovilGo Pro</h2>", unsafe_allow_html=True)
    menu = st.radio("MENÚ PRINCIPAL", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"])
    st.divider()
    st.subheader("⚙️ Configuración Temporal")
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
        <div class="main-banner">
            <h1>Bienvenido al Centro de Gestión MovilGo</h1>
            <p>Control de flota y personal operativo para el periodo {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personal Activo", "142", "Refrescado hoy")
    c2.metric("Disponibilidad", "98.2%", "+0.5%")
    c3.metric("Novedades", "2", "-1")
    c4.metric("Turnos Cubiertos", "100%", "Sin huecos")

    st.markdown("### 🚀 Acciones Rápidas")
    col_a, col_b = st.columns(2)
    with col_a:
        with st.container(border=True):
            st.markdown("#### 🔧 Planta Técnica")
            st.write("Genera la rotación T1-T2-T3 para Masters y Técnicos A/B.")
            if st.button("Configurar Planta Operativa"): st.info("Ve a la pestaña 'Gestión de Mallas'")
    with col_b:
        with st.container(border=True):
            st.markdown("#### 👥 Auxiliares de Abordaje")
            st.write("Gestiona la malla 10/10 para atención al público.")
            if st.button("Configurar Auxiliares"): st.info("Ve a la pestaña 'Gestión de Mallas'")

# --- MÓDULO GESTIÓN DE MALLAS ---
elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("⚠️ Archivo 'empleados.xlsx' no encontrado.")
    else:
        tab1, tab2 = st.tabs(["🏭 Planta Operativa", "👥 Auxiliares 10/10"])
        
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        with tab1:
            st.subheader("Parámetros de Planta Técnica")
            cols_p = st.columns(3)
            m_req = cols_p[0].number_input("Masters x Grupo", 1, 5, 2)
            ta_req = cols_p[1].number_input("Técnicos A x Grupo", 1, 15, 7)
            tb_req = cols_p[2].number_input("Técnicos B x Grupo", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                c_g = st.columns(4)
                for i in range(4):
                    with c_g[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                        es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t_b_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                # Lógica Original de Procesamiento
                mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
                tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
                tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
                
                c_list = []
                for g_id in n_map.keys():
                    g_name = n_map[g_id]
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
                g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]
                ultimo_t_disp = "T1"

                for d_i in d_info:
                    descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                    hoy_labels = {}
                    for g in g_rotan:
                        if d_i["nom"] == d_map[g]: hoy_labels[g] = "DESC. LEY"
                        else: hoy_labels[g] = res_semanal.get((g, d_i["sem"]), "T1")
                    
                    # Lógica de Disponibilidad
                    if d_i["nom"] == d_map[g_disp]: label_disp = "DESC. LEY"
                    else:
                        if descansan_hoy:
                            t_nec = hoy_labels.get(descansan_hoy[0], "T1")
                            label_disp = t_nec if ultimo_t_disp != "T3" else "APOYO T1"
                        else: label_disp = "T1"
                    
                    if "T" in label_disp: ultimo_t_disp = label_disp[:2]

                    for g in n_map.values():
                        val = label_disp if g == g_disp else hoy_labels[g]
                        for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Final": val})

                df_f = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                st.success("✅ Malla generada con éxito")
                st.dataframe(df_f.style.map(estilo_malla), use_container_width=True)

        with tab2:
            st.subheader("Gestión de Auxiliares (Equipos A-E)")
            df_aux = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
            
            if df_aux.empty:
                st.warning("No hay Auxiliares en la base de datos.")
            else:
                with st.expander("Configurar Equipos", expanded=False):
                    aux_n_map, aux_d_map = {}, {}
                    c_ax = st.columns(5)
                    for i in range(5):
                        with c_ax[i]:
                            n_eq = st.text_input(f"Eq {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                            d_eq = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                            aux_n_map[i] = n_eq; aux_d_map[n_eq] = d_eq

                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    df_aux['equipo'] = [aux_n_map[i % 5] for i in range(len(df_aux))]
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    
                    rows_ax = []
                    for d_i in d_info_ax:
                        pool = ["T1", "T2", "T1", "T2", "DISPO"]
                        # Rotación simple por semana
                        shift = d_i["sem"] % 5
                        turnos_hoy = pool[-shift:] + pool[:-shift]
                        
                        for idx, eq in enumerate(aux_n_map.values()):
                            t_f = "DESC. LEY" if d_i["nom"] == aux_d_map[eq] else turnos_hoy[idx]
                            for _, emp in df_aux[df_aux['equipo'] == eq].iterrows():
                                rows_ax.append({"Equipo": eq, "Empleado": emp['nombre'], "Label": d_i["label"], "Turno": t_f})

                    piv_ax = pd.DataFrame(rows_ax).pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                    st.dataframe(piv_ax.style.map(estilo_malla), use_container_width=True)

# --- MÓDULO BASE DE DATOS ---
elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.dataframe(df_raw, use_container_width=True)
        st.download_button("Descargar Excel", data=open("empleados.xlsx", "rb"), file_name="respaldo_empleados.xlsx")
    else:
        st.error("No se pudo cargar la base.")
