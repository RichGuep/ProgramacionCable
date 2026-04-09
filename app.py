import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión de Turnos", layout="wide", page_icon="🚀")

# --- ESTILOS PERSONALIZADOS (CSS) ---
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ffffff;
        border-radius: 5px 5px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE LOGIN ---
def login():
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False

    if not st.session_state['auth']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image("https://cdn-icons-png.flaticon.com/512/1535/1535024.png", width=100) # Icono genérico de logística
            st.title("🚀 MovilGo")
            st.subheader("Inicio de Sesión - Administrador")
            
            with st.form("login_form"):
                email = st.text_input("Correo Electrónico")
                password = st.text_input("Contraseña", type="password")
                submit = st.form_submit_button("Ingresar")
                
                if submit:
                    if email == "richard.guevara@greenmovil.com.co" and password == "Admin2026":
                        st.session_state['auth'] = True
                        st.session_state['user'] = "Richard Guevara"
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas. Intente de nuevo.")
        st.stop()

login()

# --- PANEL PRINCIPAL (Solo si está autenticado) ---
st.sidebar.title(f"👤 {st.session_state['user']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state['auth'] = False
    st.rerun()

st.title("🗓️ MovilGo: Programación de Operaciones")
st.caption("Sistema Inteligente de Optimización de Mallas y Cumplimiento Legal")

# --- 1. CARGA DE DATOS ---
@st.cache_data
def cargar_datos():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        # Mapeo de columnas
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descripcion")
        
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descripcion'})
        df['nombre'] = df['nombre'].astype(str).str.strip()
        df['cargo'] = df['cargo'].astype(str).str.strip()
        df['descripcion'] = df['descripcion'].astype(str).str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Error al cargar Excel: {e}")
        return None

df = cargar_datos()

if df is not None:
    # --- 2. CONFIGURACIÓN LATERAL ---
    with st.sidebar:
        st.header("⚙️ Parámetros de Malla")
        ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
        meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
        mes_num = meses_n.index(mes_sel) + 1
        
        cargos_disponibles = sorted(df['cargo'].unique())
        cargo_sel = st.selectbox("Cargo a programar", cargos_disponibles)
        cupo_manual = st.number_input("Cupo por turno (AM/PM/Noche)", min_value=1, value=2)
        
        st.divider()
        tipo_vista = st.radio("Modo de Visualización", ["Vista por Semanas", "Mes Completo"])

    # --- 3. LÓGICA DE CALENDARIO ---
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = []
    dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
        dias_info.append({
            "n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana,
            "label": f"{d} - {dias_esp[fecha.weekday()]}"
        })

    # --- 4. MOTOR DE OPTIMIZACIÓN ---
    if st.button(f"⚡ Generar Programación {mes_sel}"):
        df_f = df[df['cargo'] == cargo_sel].copy()
        turnos = ["AM", "PM", "Noche"]
        prob = LpProblem("MovilGo_Optimizer", LpMaximize)
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), turnos), cat='Binary')
        
        # Objetivo: Cobertura
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in turnos])

        # Restricciones
        for d_i in dias_info:
            d = d_i["n"]
            for t in turnos:
                prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) <= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            contrato = row['descripcion']
            dia_c_nom = "Sab" if "sabado" in contrato else "Dom"
            
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Ley: 2 findes libres
            f_contractuales = [di["n"] for di in dias_info if di["nombre"] == dia_c_nom]
            prob += lpSum([asig[e][d][t] for d in f_contractuales for t in turnos]) == (len(f_contractuales) - 2)
            prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 19

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            # --- POST-PROCESAMIENTO ---
            res_list = []
            for d_i in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in turnos:
                        if value(asig[e][d_i["n"]][t]) == 1: t_asig = t
                    res_list.append({
                        "Dia": d_i["n"], "Label": d_i["label"], "Semana": d_i["semana"], 
                        "Nom_Dia": d_i["nombre"], "Empleado": e, "Turno": t_asig,
                        "Contrato": df_f[df_f['nombre']==e]['descripcion'].values[0]
                    })
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
                idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
                grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
                
                f_trabajados = grupo[(grupo['Nom_Dia'] == dia_c_nom) & (grupo['Turno'] != 'DESC. CONTRATO') & (grupo['Turno'] != '---')]
                for _, row_f in f_trabajados.iterrows():
                    dia_v = row_f['Dia'] + 7
                    idx_comp = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= dia_v) & 
                                     (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].index
                    if not idx_comp.empty:
                        grupo.loc[idx_comp[0], 'Turno'] = 'DESC. L-V'
                
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
                lista_final.append(grupo)

            df_final = pd.concat(lista_final).reset_index(drop=True)
            df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

            # --- RENDERIZADO DE TABLAS ---
            def style_fn(val):
                if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
                if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
                if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
                return ''

            st.success(f"Malla de {cargo_sel} generada correctamente.")
            
            if tipo_vista == "Mes Completo":
                m_full = df_final.pivot(index='ID', columns='Label', values='Turno')
                cols_sorted = sorted(m_full.columns, key=lambda x: int(x.split(' - ')[0]))
                st.dataframe(m_full[cols_sorted].style.map(style_fn), use_container_width=True)
            else:
                sems = sorted(df_final['Semana'].unique())
                tabs = st.tabs([f"Semana {s}" for s in sems])
                for i, s in enumerate(sems):
                    with tabs[i]:
                        m_s = df_final[df_final['Semana'] == s].pivot(index='ID', columns='Label', values='Turno')
                        cols_s = sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))
                        st.dataframe(m_s[cols_s].style.map(style_fn), use_container_width=True)

            # --- AUDITORÍA ---
            with st.expander("📊 Ver Auditoría de Cumplimiento"):
                resumen = []
                for e, g in df_final.groupby("Empleado"):
                    f_trab = len(g[(g['Nom_Dia'] == ("Sab" if "sabado" in g['Contrato'].iloc[0] else "Dom")) & (g['Turno'].isin(['AM','PM','Noche']))])
                    resumen.append({
                        "Empleado": e,
                        "Findes Trabajados": f_trab,
                        "Compensatorios (L-V)": len(g[g['Turno'] == 'DESC. L-V']),
                        "Estado Ley": "✅ OK" if len(g[g['Turno'] == 'DESC. L-V']) >= f_trab else "⚠️ REVISAR"
                    })
                st.table(pd.DataFrame(resumen))
        else:
            st.error("No se pudo generar la malla. Revise los cupos.")
