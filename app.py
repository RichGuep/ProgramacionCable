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

# --- 2. RUTA DEL LOGO ---
LOGO_PATH = "MovilGo.png" 

# --- 3. ESTILOS CSS PROFESIONALES ---
st.markdown(f"""
    <style>
    /* Eliminar basura visual de Streamlit */
    [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{
        display: none !important;
    }}

    .main {{ 
        background-color: #f8fafc; 
    }}
    
    /* Tarjeta de Login */
    .login-card {{
        background-color: white;
        padding: 3rem;
        border-radius: 24px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.1);
        border: 1px solid #f1f5f9;
        text-align: center;
        max-width: 500px;
        margin: 100px auto;
    }}

    /* Logo Centrado */
    div[data-testid="stImage"] > img {{
        display: block;
        margin-left: auto;
        margin-right: auto;
    }}

    /* Títulos */
    .brand-title {{
        color: #064e3b;
        font-size: 2.5rem;
        font-weight: 850;
        margin-top: 20px;
        text-align: center;
    }}

    .brand-subtitle {{
        color: #64748b;
        font-size: 1rem;
        margin-bottom: 30px;
        text-align: center;
    }}

    /* Botón */
    .stButton>button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        color: white;
        font-weight: 700;
        height: 3.5rem;
        border: none;
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

def estilo_celdas(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold; border: 1px solid #fecaca'
    if 'T3' in v: return 'background-color: #1e293b; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0'
    if 'T2' in v: return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
    return 'color: #94a3b8; font-style: italic'

# --- 5. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False

if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=300)
        st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle">Gestión de Turnos Green Móvil</div>', unsafe_allow_html=True)
        
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Error de acceso")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- 6. APP PRINCIPAL ---
df_raw = load_base()

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, use_container_width=True)
    menu = st.radio("Menú", ["🏠 Inicio", "📊 Gestión de Mallas", "👥 Base de Datos"])
    st.divider()
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    ano_sel = st.selectbox("Año", [2025, 2026], index=1)
    mes_num = meses.index(mes_sel) + 1
    if st.button("Cerrar Sesión"):
        st.session_state['auth'] = False
        st.rerun()

if menu == "🏠 Inicio":
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #064e3b 0%, #10b981 100%); padding: 3rem; border-radius: 20px; color: white; text-align: center;">
            <h1>Bienvenido Richard</h1>
            <p>Control Operativo - {mes_sel} {ano_sel}</p>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Personal", "145", "Activos")
    c2.metric("Estado", "Óptimo", "Flota")
    c3.metric("Mallas", "Sincronizadas", "Hoy")

elif menu == "📊 Gestión de Mallas":
    if df_raw is None:
        st.error("No se encontró empleados.xlsx")
    else:
        t1, t2 = st.tabs(["🏭 Planta Técnica", "👥 Auxiliares"])
        DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        
        with t1:
            st.subheader("Configuración Técnica")
            cols = st.columns(3)
            m_req = cols[0].number_input("Masters", 1, 5, 2)
            ta_req = cols[1].number_input("Tec A", 1, 15, 7)
            tb_req = cols[2].number_input("Tec B", 1, 10, 3)

            n_map, d_map, t_map = {}, {}, {}
            cg = st.columns(4)
            for i in range(4):
                with cg[i]:
                    n_s = st.text_input(f"Grupo {i+1}", f"G{i+1}", key=f"gn_{i}")
                    d_s = st.selectbox(f"Descanso", DIAS, index=i%7, key=f"gd_{i}")
                    is_d = st.checkbox("Disp", value=(i==3), key=f"gt_{i}")
                    n_map[f"G{i+1}"] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if is_d else "ROTA"

            if st.button("Generar Malla Técnica"):
                # Filtrar personal
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

                prob = LpProblem("Malla", LpMinimize)
                asig = LpVariable.dicts("Asig", (g_rotan, semanas, ["T1","T2","T3"]), cat='Binary')
                for s in semanas:
                    for t in ["T1","T2","T3"]: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
                    for g in g_rotan: prob += lpSum([asig[g][s][t] for t in ["T1","T2","T3"]]) == 1
                prob.solve(PULP_CBC_CMD(msg=0))
                res_sem = {(g, s): t for g in g_rotan for s in semanas for t in ["T1","T2","T3"] if value(asig[g][s][t]) == 1}

                final_rows = []
                g_disp_name = [g for g in n_map.values() if t_map[g] == "DISP"][0]
                for d_i in d_info:
                    desc_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
                    # CORRECCIÓN DE LA LÍNEA DEL ERROR:
                    hoy_vals = {g: ("DESC. LEY" if d_i["nom"] == d_map[g] else res_sem.get((g, d_i["sem"]), "T1")) for g in g_rotan}
                    label_disp = hoy_vals.get(desc_hoy[0], "T1") if desc_hoy else "T1"
                    for g in n_map.values():
                        val = label_disp if g == g_disp_name else hoy_vals.get(g, "T1")
                        for _, m in df_cel[df_cel['grupo'] == g].iterrows():
                            final_rows.append({"Grupo": g, "Empleado": m['nombre'], "Cargo": m['cargo'], "Label": d_i["label"], "Turno": val})
                
                df_piv = pd.DataFrame(final_rows).pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Turno')
                st.dataframe(df_piv.style.map(estilo_celdas), use_container_width=True)

        with t2:
            st.subheader("Auxiliares")
            df_ax = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy()
            if not df_ax.empty:
                if st.button("Generar Malla Auxiliares"):
                    # Lógica 10/10 simple
                    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                    d_info_ax = [{"nom": DIAS[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                    rows_ax = []
                    for d_i in d_info_ax:
                        for _, emp in df_ax.iterrows():
                            rows_ax.append({"Empleado": emp['nombre'], "Label": d_i["label"], "Turno": "T1"})
                    st.dataframe(pd.DataFrame(rows_ax).pivot(index='Empleado', columns='Label', values='Turno').style.map(estilo_celdas), use_container_width=True)

elif menu == "👥 Base de Datos":
    st.header("Personal")
    if df_raw is not None: st.dataframe(df_raw, use_container_width=True)
