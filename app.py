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

# --- 2. RUTA DEL LOGO (Basado en tu GitHub) ---
LOGO_PATH = "MovilGo.png" 

# --- 3. ESTILOS CSS PROFESIONALES (Centrado y Limpieza UX) ---
st.markdown(f"""
    <style>
    /* Ocultar elementos nativos de Streamlit que ensucian el diseño */
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
        display: none !important;
    }}

    .main {{ 
        background-color: #f8fafc; 
    }}
    
    /* Tarjeta de Login Centrada */
    .login-card {{
        background-color: white;
        padding: 4rem;
        border-radius: 24px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.1);
        border: 1px solid #f1f5f9;
        text-align: center;
        max-width: 550px;
        margin: 100px auto; /* Centrado perfecto vertical/horizontal */
    }}

    /* Forzar centrado de la imagen */
    div[data-testid="stImage"] > img {{
        display: block;
        margin-left: auto;
        margin-right: auto;
        border-radius: 10px;
    }}

    /* Tipografía Personalizada */
    .brand-title {{
        color: #064e3b;
        font-size: 2.8rem;
        font-weight: 850;
        margin-top: 25px;
        margin-bottom: 5px;
        letter-spacing: -1px;
    }}

    .brand-subtitle {{
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 35px;
        font-weight: 400;
    }}

    /* Estilo de Inputs y Botones */
    .stButton>button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 700;
        border: none;
        padding: 0.8rem;
        font-size: 1.1rem;
        margin-top: 15px;
        transition: transform 0.2s;
    }}
    .stButton>button:hover {{
        transform: scale(1.02);
        color: white;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 4. FUNCIONES DE DATOS Y ESTILO ---
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

def estilo_celdas(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fecaca'
    if 'T3' in v: return 'background-color: #1e293b; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0'
    if 'T2' in v: return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
    return 'color: #94a3b8; font-style: italic'

# --- 5. PANTALLA DE LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        
        # Logo Centrado
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=320)
        
        # Título y Subtítulo Centrados
        st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle">Planificador de Turnos Green Móvil</div>', unsafe_allow_html=True)
        
        with st.form("Login"):
            u = st.text_input("Usuario Corporativo", placeholder="ejemplo@greenmovil.com.co")
            p = st.text_input("Contraseña", type="password", placeholder="••••••••")
            submit = st.form_submit_button("INGRESAR AL PANEL")
            
            if submit:
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 6. PANEL DE CONTROL (POST-LOGIN) ---
df_raw = load_base()

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    st.markdown("<h3 style='text-align:center;'>Panel de Control</h3>", unsafe_allow_html=True)
    menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"], label_visibility="collapsed")
    
    st.divider()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes de Gestión", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    mes_num = meses.index(mes_sel) + 1
    
    if st.button("🚪 Cerrar Sesión"):
        st.session_state['auth'] = False
        st.rerun()

# --- MÓDULO INICIO ---
if menu == "🏠 Inicio":
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center; margin-bottom: 2rem;">
            <h1 style='font-size: 3rem; margin-bottom: 0;'>Bienvenido Richard</h1>
            <p style='font-size: 1.2rem; opacity: 0.9;'>Gestión Operativa para {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Personal Técnico", "Planta Completa", "Activo")
    c2.metric("Auxiliares", "10/10", "Programados")
    c3.metric("Novedades", "0", "Sin Alertas")
    c4.metric("Sincronización", "Excel OK", "Hoy")

# --- MÓDULO MALLAS (Lógica Completa) ---
elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("Archivo 'empleados.xlsx' no encontrado.")
    else:
        tab1, tab2 = st.tabs(["🏭 Planta Operativa (T1-T3)", "👥 Auxiliares de Abordaje"])
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

        with tab1:
            st.subheader("Configuración de Planta Técnica")
            cols = st.columns(3)
            m_req = cols[0].number_input("Masters", 1, 5, 2)
            ta_req = cols[1].number_input("Técnicos A", 1, 15, 7)
            tb_req = cols[2].number_input("Técnicos B", 1, 10, 3)

            with st.expander("📅 Grupos y Descansos Legales", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                c_g = st.columns(4)
                for i in range(4):
                    with c_g[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"t1_n_{i}")
                        d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"t1_d_{i}")
                        es_disp = st.checkbox("Disponibilidad", value=(i==3), key=f"t1_t_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICA"):
                # Filtrado por cargos
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
                
                df_cel = pd.DataFrame(c_list)
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
                    hoy_vals = {{g: ("DESC. LEY" if d_i["nom"] == d_map[g] else res_semanal.get((g, d_i["sem"]), "T1")) for g in g_rotan}}
                    label_disp = hoy_vals.get(desc_hoy[0], "T1") if desc_hoy else "T1"
                    for g in n_map.values():
                        val = label_disp if g == g_disp_name else hoy_vals[g]
                        for _, m in df_cel[df_cel['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val})

                df_piv = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                cols_sorted = sorted(df_piv.columns, key=lambda x: int(x.split('-')[0]))
                st.dataframe(df_piv[cols_sorted].style.map(estilo_celdas), use_container_width=True)

        with tab2:
            st.subheader("Malla Auxiliares (10/10)")
            df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
            if not df_ax.empty:
                with st.expander("Configurar Equipos", expanded=False):
                    ax_map, ax_desc = {}, {}
                    c_ax = st.columns(5)
                    for i in range(5):
                        with c_ax[i]:
                            ne = st.text_input(f"Eq {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                            de = st.selectbox(f"Descanso", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                            ax_map[i] = ne; ax_desc[ne] = de

                if st.button("⚡ GENERAR MALLA AUXILIARES"):
                    df_ax['equipo'] = [ax_map[i % 5] for i in range(len(df_ax))]
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    rows_ax = []
                    pool = ["T1", "T2", "T1", "T2", "DISPO"]
                    for d_i in d_info_ax:
                        shift = d_i["sem"] % 5
                        turnos_hoy = pool[-shift:] + pool[:-shift]
                        for idx, eq in enumerate(ax_map.values()):
                            t_f = "DESC. LEY" if d_i["nom"] == ax_desc[eq] else turnos_hoy[idx]
                            for _, emp in df_ax[df_ax['equipo'] == eq].iterrows():
                                rows_ax.append({"Equipo": eq, "Empleado": emp['nombre'], "Label": d_i["label"], "Turno": t_f})
                    piv_ax = pd.DataFrame(rows_ax).pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                    cols_ax_sorted = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))
                    st.dataframe(piv_ax[cols_ax_sorted].style.map(estilo_celdas), use_container_width=True)

# --- BASE DE DATOS ---
elif menu == "👥 Base de Datos":
    st.header("Base de Datos Maestra")
    if df_raw is not None:
        st.dataframe(df_raw, use_container_width=True)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_raw.to_excel(writer, index=False)
        st.download_button("📥 Descargar Base de Datos", data=buffer.getvalue(), file_name="base_empleados.xlsx")
