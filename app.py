import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Gestión Humana", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .metric-card { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid #2563eb; text-align: center; }
    .metric-val { font-size: 1.6rem; font-weight: bold; color: #1e293b; }
    .metric-title { font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br><h1 style='text-align:center; color:#1a365d;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("ACCEDER AL SISTEMA"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. CARGA DE DATOS ---
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
        st.header("⚙️ Configuración Operativa")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo a Programar", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Técnicos por Turno", 1, 15, 2)
        peso_estabilidad = st.slider("Estabilidad de Bloques", 1, 100, 60)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    
    dias_info = []
    for d in dias_range:
        dt = datetime(ano_sel, mes_num, d)
        dias_info.append({
            "n": d, 
            "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][dt.weekday()], 
            "semana": dt.isocalendar()[1],
            "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][dt.weekday()]}"
        })
    
    semanas_del_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("🚀 GENERAR MALLA CON DESCANSOS OPTIMIZADOS"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        nombres = df_f['nombre'].tolist()
        
        prob = LpProblem("MovilGo_Final", LpMaximize)
        asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
        mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
        trabajo_noche_sem = LpVariable.dicts("NocheSem", (nombres, semanas_del_mes), cat='Binary')
        
        # FO: Max asignación + Estabilidad
        prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

        for d in dias_range:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

        for e in nombres:
            row = df_f[df_f['nombre'] == e].iloc[0]
            dia_ley_pref = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            
            # Control de Noches (Máximo 2 semanas)
            for s in semanas_del_mes:
                dias_sem = [di["n"] for di in dias_info if di["semana"] == s]
                for d in dias_sem: prob += trabajo_noche_sem[e][s] >= asig[e][d]["Noche"]
            prob += lpSum([trabajo_noche_sem[e][s] for s in semanas_del_mes]) <= 2

            for d in dias_range:
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d > 1:
                    for t in LISTA_TURNOS:
                        prob += mantiene[e][d][t] <= asig[e][d][t]
                        prob += mantiene[e][d][t] <= asig[e][d-1][t]
                
                # Higiene sueño
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                    prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            # Garantía de Ley: Forzamos al menos 2 descansos en su día preferido (Sab o Dom)
            dias_ley_mes = [di["n"] for di in dias_info if di["nombre"] == dia_ley_pref]
            prob += lpSum([asig[e][d][t] for d in dias_ley_mes for t in LISTA_TURNOS]) <= (len(dias_ley_mes) - 2)
            
            # Carga mínima razonable
            prob += lpSum([asig[e][d][t] for d in dias_range for t in LISTA_TURNOS]) >= 16

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
                
                # 1. Asignar DESC. LEY (Prioridad 1)
                idx_libres_ley = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_l)].index
                # Marcamos todos los que el motor dejó libres como Ley
                grupo.loc[idx_libres_ley, 'Turno'] = 'DESC. LEY'
                
                # 2. Asignar COMPENSATORIOS (Si trabajó el día de ley)
                dias_trabajados_ley = grupo[(grupo['Nom_Dia'] == dia_l) & (grupo['Turno'].isin(LISTA_TURNOS))]
                for _, row_f in dias_trabajados_ley.iterrows():
                    # Buscar el primer hueco disponible en los 6 días siguientes (que no sea otro finde)
                    hueco = grupo[(grupo['Dia'] > row_f['Dia']) & 
                                  (grupo['Dia'] <= row_f['Dia'] + 6) & 
                                  (grupo['Turno'] == '---') & 
                                  (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1)
                    if not hueco.empty:
                        grupo.loc[hueco.index, 'Turno'] = 'DESC. COMPENSATORIO'

                # 3. Post-Noche
                for i in range(len(grupo)-1):
                    if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                        grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                
                # 4. Convertir Disponibilidad sobrante en "DESCANSO ADICIONAL" para que la gente esté feliz
                grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DESC. ADICIONAL'
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final)
            st.success("✅ Malla generada: Disponibilidades convertidas en descansos.")

    # --- 5. INTERFAZ Y REPORTES ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        # KPIs mejorados
        st.subheader("📊 Métricas de Bienestar Laboral")
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Ley</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. LEY'])}</div></div>", unsafe_allow_html=True)
        with k2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Compensatorios</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. COMPENSATORIO'])}</div></div>", unsafe_allow_html=True)
        with k3: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Extra</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. ADICIONAL'])}</div></div>", unsafe_allow_html=True)
        with k4: 
            p_noche = (len(df_v[df_v['Turno'] == 'Noche']) / len(df_v[df_v['Turno'].isin(LISTA_TURNOS)])) * 100 if len(df_v[df_v['Turno'].isin(LISTA_TURNOS)]) > 0 else 0
            st.markdown(f"<div class='metric-card'><div class='metric-title'>% Carga Nocturna</div><div class='metric-val'>{p_noche:.1f}%</div></div>", unsafe_allow_html=True)

        t1, t2, t3 = st.tabs(["📅 Malla Maestra", "⚖️ Auditoría de Descansos", "📥 Exportar"])

        with t1:
            def style_map(v):
                if v == 'DESC. LEY': return 'background-color: #fecaca; color: #991b1b; font-weight: bold; border: 1px solid #f87171'
                if v == 'DESC. COMPENSATORIO': return 'background-color: #fef08a; color: #854d0e; font-weight: bold'
                if v == 'DESC. POST-NOCHE': return 'background-color: #bbf7d0; color: #166534; font-weight: bold'
                if v == 'DESC. ADICIONAL': return 'background-color: #e2e8f0; color: #475569; font-style: italic'
                if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
                return 'background-color: white; color: #1e293b'
            
            m_f = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            cols = sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))
            st.dataframe(m_f[cols].style.map(style_map), use_container_width=True)

        with t2:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                dia_l = "Sab" if "sab" in str(g['Ley'].iloc[0]).lower() else "Dom"
                trab_ley = len(g[(g['Nom_Dia'] == dia_l) & (g['Turno'].isin(LISTA_TURNOS))])
                audit.append({
                    "Empleado": e, "Contrato": f"Descansa {dia_l}",
                    "Descansos Ley": len(g[g['Turno'] == 'DESC. LEY']),
                    "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']),
                    "Descansos Extras": len(g[g['Turno'] == 'DESC. ADICIONAL']),
                    "Efectividad": "✅ 100%" if len(g[g['Turno'] == 'DESC. COMPENSATORIO']) >= trab_ley else "⚠️ Revisar"
                })
            st.table(pd.DataFrame(audit))

        with t3:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                m_f[cols].to_excel(writer, sheet_name='Malla_Turnos')
                pd.DataFrame(audit).to_excel(writer, sheet_name='Reporte_Descansos', index=False)
            st.download_button(label="📥 Descargar Reporte para Nómina (Excel)", data=output.getvalue(), file_name=f"Programacion_{mes_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
