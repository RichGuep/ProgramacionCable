import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Control Operativo", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; border-top: 5px solid #1e293b; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .metric-val { font-size: 1.6rem; font-weight: bold; color: #1e293b; }
    .metric-title { font-size: 0.8rem; color: #64748b; text-transform: uppercase; }
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
                user = st.text_input("Usuario")
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
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo por Turno", 1, 15, 2)
        peso_estabilidad = st.slider("Estabilidad de Turno", 1, 100, 60)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("🚀 GENERAR MALLA 2+2"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        nombres = df_f['nombre'].tolist()
        
        prob = LpProblem("MovilGo_2_2", LpMaximize)
        asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
        mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
        noche_sem = LpVariable.dicts("NocheSem", (nombres, semanas_mes), cat='Binary')
        
        prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

        for d in dias_range:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

        for e in nombres:
            row = df_f[df_f['nombre'] == e].iloc[0]
            dia_ley_pref = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # Máximo 2 semanas de noche
            for s in semanas_mes:
                d_s = [di["n"] for di in dias_info if di["semana"] == s]
                for d in d_s: prob += noche_sem[e][s] >= asig[e][d]["Noche"]
            prob += lpSum([noche_sem[e][s] for s in semanas_mes]) <= 2

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
            
            # Restricción de Ley: Obligatorio 2 descansos en su día de ley
            d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_ley_pref]
            prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)
            prob += lpSum([asig[e][d][t] for d in dias_range for t in LISTA_TURNOS]) >= 18 # Ajuste carga operativa

        prob.solve(PULP_CBC_CMD(msg=0))

        if LpStatus[prob.status] == 'Optimal':
            res_list = []
            for di in dias_info:
                for e in nombres:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").copy()
                dia_l = "Sab" if "sab" in str(grupo['Ley'].iloc[0]).lower() else "Dom"
                
                # 1. Aplicar exactamente 2 DESC. LEY
                idx_libres_ley = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_l)].head(2).index
                grupo.loc[idx_libres_ley, 'Turno'] = 'DESC. LEY'
                
                # 2. Aplicar COMPENSATORIOS por trabajar en día de ley
                dias_trab_ley = grupo[(grupo['Nom_Dia'] == dia_l) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, r_f in dias_trab_ley.iterrows():
                    hueco = grupo[(grupo['Dia'] > r_f['Dia']) & (grupo['Dia'] <= r_f['Dia'] + 6) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                    if not hueco.empty: grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'

                # 3. Post-Noche
                for i in range(len(grupo)-1):
                    if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                        grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                
                # 4. TODO LO DEMÁS ES DISPONIBILIDAD
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final)
            st.success("✅ Malla 2+2 generada con Disponibilidad operativa.")

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        # KPIs de Control
        st.subheader("📊 Control de Malla (4 Descansos/Mes)")
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Ley</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. LEY'])}</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Compensatorios</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. COMPENSATORIO'])}</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='metric-card'><div class='metric-title'>Personal en Disponibilidad</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DISPONIBILIDAD'])}</div></div>", unsafe_allow_html=True)
        with k4: st.markdown(f"<div class='metric-card'><div class='metric-title'>Turnos Noche</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'Noche'])}</div></div>", unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "⚖️ Auditoría Legal", "📥 Reportes"])

        with t1:
            def style_map(v):
                if v == 'DESC. LEY': return 'background-color: #fecaca; color: #991b1b; font-weight: bold'
                if v == 'DESC. COMPENSATORIO': return 'background-color: #fef08a; color: #854d0e; font-weight: bold'
                if v == 'DESC. POST-NOCHE': return 'background-color: #dcfce7; color: #166534; font-weight: bold'
                if v == 'DISPONIBILIDAD': return 'color: #3b82f6; font-weight: normal'
                if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
                return 'color: #1e293b'
            
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            cols = sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))
            st.dataframe(m_f[cols].style.map(style_map), use_container_width=True)

        with t2:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                dia_l = "Sab" if "sab" in str(g['Ley'].iloc[0]).lower() else "Dom"
                audit.append({
                    "Empleado": e, "Contrato": f"Descansa {dia_l}",
                    "Desc. Ley (Objetivo 2)": len(g[g['Turno'] == 'DESC. LEY']),
                    "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']),
                    "Total Descansos": len(g[g['Turno'].str.contains('DESC')]),
                    "Estado": "✅ Cumple" if len(g[g['Turno'].str.contains('DESC')]) >= 4 else "⚠️ Revisar"
                })
            st.table(pd.DataFrame(audit))

        with t3:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                m_f[cols].to_excel(writer, sheet_name='Malla')
                pd.DataFrame(audit).to_excel(writer, sheet_name='Auditoria', index=False)
            st.download_button(label="📥 Descargar Programación Excel", data=output.getvalue(), file_name=f"Malla_MovilGo_Final.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
