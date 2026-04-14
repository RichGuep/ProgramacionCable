import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Analytics", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS CORPORATIVOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; text-align: center; }
    .metric-val { font-size: 1.8rem; font-weight: bold; color: #2563eb; }
    .metric-title { font-size: 0.9rem; color: #64748b; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br><h1 style='text-align:center;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. MOTOR DE OPTIMIZACIÓN ---
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
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)
        peso_estabilidad = st.slider("Estabilidad de Turno", 1, 100, 40)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]

    if st.button("🚀 GENERAR MALLA Y AUDITAR"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        nombres = df_f['nombre'].tolist()
        
        prob = LpProblem("MovilGo_Final", LpMaximize)
        asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
        mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
        
        prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

        for d in dias_range:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

        for e in nombres:
            row = df_f[df_f['nombre'] == e].iloc[0]
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            for d in dias_range:
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d > 1:
                    for t in LISTA_TURNOS:
                        prob += mantiene[e][d][t] <= asig[e][d][t]
                        prob += mantiene[e][d][t] <= asig[e][d-1][t]
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_ley]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)
            prob += lpSum([asig[e][d][t] for d in dias_range for t in LISTA_TURNOS]) >= 15

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for d_idx in dias_info:
                for e in nombres:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][d_idx["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": d_idx["n"], "Label": d_idx["label"], "Nom_Dia": d_idx["nombre"], "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_l = "Sab" if "sab" in str(grupo['Ley'].iloc[0]).lower() else "Dom"
                # Marcar Ley
                idx_fijos = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_l)].head(2).index
                grupo.loc[idx_fijos, 'Turno'] = 'DESC. LEY'
                # Marcar Compensatorios
                findes_trab = grupo[(grupo['Nom_Dia'] == dia_l) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, r_f in findes_trab.iterrows():
                    hueco = grupo[(grupo['Dia'] > r_f['Dia']) & (grupo['Dia'] <= r_f['Dia'] + 7) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                    if not hueco.empty: grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'
                # Post Noche
                for i in range(len(grupo)-1):
                    if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                        grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final)

    # --- 5. VISUALIZACIÓN Y KPIS ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']

        # --- SECCIÓN KPIs ---
        st.subheader("📊 Indicadores Clave de Desempeño (KPIs)")
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            total_asig = len(df_v[df_v['Turno'].isin(LISTA_TURNOS)])
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Turnos Asignados</div><div class='metric-val'>{total_asig}</div></div>", unsafe_allow_html=True)
        with k2:
            desc_ley = len(df_v[df_v['Turno'] == 'DESC. LEY'])
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos de Ley</div><div class='metric-val'>{desc_ley}</div></div>", unsafe_allow_html=True)
        with k3:
            comp_tot = len(df_v[df_v['Turno'] == 'DESC. COMPENSATORIO'])
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Compensatorios</div><div class='metric-val'>{comp_tot}</div></div>", unsafe_allow_html=True)
        with k4:
            util_noche = len(df_v[df_v['Turno'] == 'Noche'])
            st.markdown(f"<div class='metric-card'><div class='metric-title'>Cobertura Noche</div><div class='metric-val'>{util_noche}</div></div>", unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "⚖️ Auditoría Legal", "📥 Descargas"])

        with t1:
            def style_map(v):
                if v == 'DESC. LEY': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
                if v == 'DESC. COMPENSATORIO': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
                if v == 'DESC. POST-NOCHE': return 'background-color: #d1fae5; color: #065f46; font-weight: bold'
                if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
                if v == 'DISPONIBILIDAD': return 'color: #94a3b8'
                return ''
            
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            cols = sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))
            st.dataframe(m_f[cols].style.map(style_map), use_container_width=True)

        with t2:
            st.subheader("Auditoría por Persona")
            audit_data = []
            for e, g in df_v.groupby("Empleado"):
                dia_l = "Sab" if "sab" in str(g['Ley'].iloc[0]).lower() else "Dom"
                f_t = len(g[(g['Nom_Dia'] == dia_l) & (g['Turno'].isin(LISTA_TURNOS))])
                audit_data.append({
                    "Empleado": e,
                    "Día Ley": dia_l,
                    "Días Ley Trabajados": f_t,
                    "Descansos Ley Tomados": len(g[g['Turno'] == 'DESC. LEY']),
                    "Compensatorios Asignados": len(g[g['Turno'] == 'DESC. COMPENSATORIO']),
                    "Turnos AM": len(g[g['Turno'] == 'AM']),
                    "Turnos PM": len(g[g['Turno'] == 'PM']),
                    "Turnos Noche": len(g[g['Turno'] == 'Noche']),
                    "Estado": "✅ OK" if len(g[g['Turno'] == 'DESC. COMPENSATORIO']) >= f_t else "⚠️ Pendiente"
                })
            st.table(pd.DataFrame(audit_data))

        with t3:
            st.subheader("Exportar Datos")
            # Excel Download
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                m_f[cols].to_excel(writer, sheet_name='Malla')
                pd.DataFrame(audit_data).to_excel(writer, sheet_name='Auditoria', index=False)
            
            st.download_button(
                label="📥 Descargar Malla en Excel",
                data=output.getvalue(),
                file_name=f"Malla_{mes_sel}_{ano_sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.info("Para obtener PDF, puedes imprimir la página (Ctrl+P) o guardar el Excel como PDF.")
