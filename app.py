import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Auditoría Reforma Laboral", layout="wide", page_icon="⚖️")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border-top: 5px solid #1e293b; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-val { font-size: 1.5rem; font-weight: bold; color: #1e293b; }
    .metric-title { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
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
        st.header("⚙️ Parámetros Operativos")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 20, 2)
        peso_estabilidad = st.slider("Rigidez de Bloques (Estabilidad)", 50, 300, 150)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button(f"🚀 GENERAR MALLA Y AUDITORÍA: {cargo_sel}"):
        with st.status("Ejecutando motor de optimización legal...", expanded=True) as status:
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            prog = st.progress(0)
            
            prob = LpProblem("MovilGo_Laboral", LpMaximize)
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
            
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                    lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                dl_val = str(row['descanso_ley']).lower()
                dia_ley_pref = "Vie" if "vie" in dl_val else ("Sab" if "sab" in dl_val else "Dom")

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

                d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_ley_pref]
                prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)

            prog.progress(50)
            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=45, gapRel=0.05))

            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                res_list = []
                for di in dias_info:
                    for e in nombres:
                        t_asig = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[e][di["n"]][t]) == 1: t_asig = t
                        res_list.append({
                            "Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], 
                            "Semana": di["semana"], "Empleado": e, "Turno": t_asig, 
                            "Contrato": df_f[df_f['nombre']==e]['descanso_ley'].values[0]
                        })
                
                df_res = pd.DataFrame(res_list)
                lista_final = []
                
                for emp, grupo in df_res.groupby("Empleado"):
                    grupo = grupo.sort_values("Dia").copy()
                    lv = str(grupo['Contrato'].iloc[0]).lower()
                    dl = "Vie" if "vie" in lv else ("Sab" if "sab" in lv else "Dom")
                    
                    semanas_a_compensar = []
                    for sem in semanas_mes:
                        dia_l_sem = grupo[(grupo['Semana'] == sem) & (grupo['Nom_Dia'] == dl)]
                        if not dia_l_sem.empty and dia_l_sem['Turno'].iloc[0] in LISTA_TURNOS:
                            semanas_a_compensar.append(sem)

                    idx_l = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dl)].head(2).index
                    grupo.loc[idx_l, 'Turno'] = 'DESC. LEY'

                    for sem_trabajada in semanas_a_compensar:
                        idx_comp = grupo[(grupo['Semana'] == sem_trabajada + 1) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1).index
                        if not idx_comp.empty:
                            grupo.loc[idx_comp, 'Turno'] = 'DESC. COMPENSATORIO'

                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] != 'Noche':
                            actual = grupo.iloc[i+1]['Turno']
                            if 'DESC' in str(actual) or actual == '---':
                                etiqueta = f"POST-NOCHE ({actual})" if actual != '---' else "DESC. POST-NOCHE"
                                grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = etiqueta

                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                prog.progress(100)
                status.update(label="✅ Análisis de Reforma y Malla Completados.", state="complete", expanded=False)

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        # --- BLOQUE DE INDICADORES (KPIs) ---
        st.subheader("📊 Resumen de Control")
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Ley</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. LEY'])}</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Compensatorios</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. COMPENSATORIO'])}</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='metric-card'><div class='metric-title'>En Disponibilidad</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DISPONIBILIDAD'])}</div></div>", unsafe_allow_html=True)
        with k4: st.markdown(f"<div class='metric-card'><div class='metric-title'>Noches Programadas</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'Noche'])}</div></div>", unsafe_allow_html=True)

        tab_m, tab_audit, tab_repo = st.tabs(["📅 Malla Operativa", "⚖️ Auditoría Reforma Laboral", "📥 Reportes"])

        with tab_m:
            def style_v(v):
                if 'LEY' in v: return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMPENSATORIO' in v: return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if 'POST-NOCHE' in v: return 'background-color: #dcfce7; color: #166534; font-weight: bold'
                if v == 'Noche': return 'background-color: #1e293b; color: white'
                if v == 'DISPONIBILIDAD': return 'color: #3b82f6'
                return ''
            
            m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            cols_ord = sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))
            st.dataframe(m_piv[cols_ord].style.map(style_v), use_container_width=True)

        with tab_audit:
            st.markdown("### 📋 Verificación de Cumplimiento (Ley 2101 / Reforma)")
            audit_list = []
            for e, g in df_v.groupby("Empleado"):
                total_desc = len(g[g['Turno'].str.contains('DESC')])
                d_ley = len(g[g['Turno'].str.contains('LEY')])
                d_comp = len(g[g['Turno'].str.contains('COMPENSATORIO')])
                
                audit_list.append({
                    "Empleado": e,
                    "Día de Contrato": g['Contrato'].iloc[0],
                    "Descansos de Ley (Min 2)": d_ley,
                    "Compensatorios (1 x sem trabajada)": d_comp,
                    "Total Descansos Mes": total_desc,
                    "Estado": "✅ CUMPLE" if total_desc >= 4 else "⚠️ REVISAR"
                })
            
            df_audit = pd.DataFrame(audit_list)
            st.table(df_audit)

        with tab_repo:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                m_piv[cols_ord].to_excel(writer, sheet_name='Malla_Final')
                df_audit.to_excel(writer, sheet_name='Auditoria_Legal', index=False)
            st.download_button("📥 Descargar Reporte Completo (Excel)", output.getvalue(), f"Malla_{cargo_sel}_{mes_sel}.xlsx")
