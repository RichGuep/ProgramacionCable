import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - 100% Cumplimiento", layout="wide", page_icon="⚖️")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border-top: 5px solid #1e293b; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        c_des = next((c for c in df.columns if 'des' in c), "descanso")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo', c_des: 'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Parámetros")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 20, 2)
        peso_estabilidad = st.select_slider("Estabilidad de Bloques", options=[50, 100, 150, 200, 300], value=150)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button(f"🚀 GENERAR MALLA 100% LEGAL"):
        with st.status("Garantizando 1 descanso por semana...", expanded=True) as status:
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            
            prob = LpProblem("Malla_Garantizada", LpMaximize)
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
            
            # OBJETIVO: Maximizar turnos pero con peso fuerte en estabilidad
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                    lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                dl_val = str(row['descanso_ley']).lower()
                dia_l_pref = "Vie" if "vie" in dl_val else ("Sab" if "sab" in dl_val else "Dom")

                for d in dias_range:
                    prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                    if d > 1:
                        for t in LISTA_TURNOS:
                            prob += mantiene[e][d][t] <= asig[e][d][t]
                            prob += mantiene[e][d][t] <= asig[e][d-1][t]
                    
                    if d < num_dias:
                        prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

                # REGLA MAESTRA: Forzar un descanso mínimo por cada semana del mes
                for sem in semanas_mes:
                    dias_de_la_semana = [di["n"] for di in dias_info if di["semana"] == sem]
                    # La suma de turnos en la semana debe ser <= (días de la semana - 1)
                    prob += lpSum([asig[e][d][t] for d in dias_de_la_semana for t in LISTA_TURNOS]) <= (len(dias_de_la_semana) - 1)

            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45, gapRel=0.05))

            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                res_list = []
                for di in dias_info:
                    for e in nombres:
                        t_asig = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[e][di["n"]][t]) == 1: t_asig = t
                        res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Semana": di["semana"], "Empleado": e, "Turno": t_asig, "Contrato": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
                
                df_res = pd.DataFrame(res_list)
                lista_final = []
                
                for emp, grupo in df_res.groupby("Empleado"):
                    grupo = grupo.sort_values("Dia").copy()
                    lv = str(grupo['Contrato'].iloc[0]).lower()
                    dl = "Vie" if "vie" in lv else ("Sab" if "sab" in lv else "Dom")
                    
                    # 1. Asignación de Descansos Semanales
                    for sem in semanas_mes:
                        f_sem = grupo[grupo['Semana'] == sem]
                        # Buscar si ya hay un hueco (---)
                        hueco = f_sem[f_sem['Turno'] == '---']
                        
                        if not hueco.empty:
                            # Si el hueco está en su día de contrato, es DESC. LEY
                            if dl in hueco['Nom_Dia'].values:
                                idx = hueco[hueco['Nom_Dia'] == dl].index
                                grupo.loc[idx, 'Turno'] = 'DESC. LEY'
                            else:
                                # Si el hueco está en otro día, es COMPENSATORIO
                                grupo.loc[hueco.head(1).index, 'Turno'] = 'DESC. COMPENSATORIO'
                    
                    # 2. Post-Noche
                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and 'DESC' not in str(grupo.iloc[i+1]['Turno']):
                            if grupo.iloc[i+1]['Turno'] == '---':
                                grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'

                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                status.update(label="✅ Malla generada: 1 descanso por semana garantizado.", state="complete", expanded=False)

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        tab_m, tab_audit = st.tabs(["📅 Malla Operativa", "⚖️ Auditoría Legal"])
        
        with tab_m:
            def style_v(v):
                if 'LEY' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMPENSATORIO' in v: return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if 'POST-NOCHE' in v: return 'background-color: #dcfce7; color: #166534; font-weight: bold'
                if v == 'Noche': return 'background-color: #1e293b; color: white'
                return ''
            
            m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            st.dataframe(m_piv[sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))].style.map(style_v), use_container_width=True)

        with tab_audit:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                d_ley = len(g[g['Turno'] == 'DESC. LEY'])
                d_comp = len(g[g['Turno'] == 'DESC. COMPENSATORIO'])
                total = d_ley + d_comp
                # Meta: tantas semanas como tenga el mes
                audit.append({
                    "Empleado": e, 
                    "Contrato": g['Contrato'].iloc[0], 
                    "Descansos Ley": d_ley, 
                    "Compensatorios": d_comp,
                    "Total Descansos": total,
                    "Semanas del Mes": len(semanas_mes),
                    "Estado": "✅ CUMPLE" if total >= len(semanas_mes) else "⚠️ REVISAR CUPOS"
                })
            st.table(pd.DataFrame(audit))
