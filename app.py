import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro - Control Operativo", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS PERSONALIZADOS ---
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

# --- 3. SISTEMA DE AUTENTICACIÓN ---
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
    except Exception as e:
        st.error(f"Error al cargar 'empleados.xlsx': {e}")
        return None

df_raw = load_data()

# --- 5. INTERFAZ PRINCIPAL Y LÓGICA ---
if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses_nombres, index=datetime.now().month - 1)
        mes_num = meses_nombres.index(mes_sel) + 1
        
        cargo_sel = st.selectbox("Cargo a Programar", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Cupo máximo por Turno", 1, 30, 2)
        peso_estabilidad = st.slider("Preferencia: Estabilidad de Turno", 1, 100, 60)

    # Cálculo de días del mes
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_nombres_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    
    dias_info = []
    for d in dias_range:
        fecha = datetime(ano_sel, mes_num, d)
        idx_dia = fecha.weekday()
        dias_info.append({
            "n": d, 
            "nombre": dias_nombres_es[idx_dia], 
            "semana": fecha.isocalendar()[1], 
            "label": f"{d} - {dias_nombres_es[idx_dia]}"
        })
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    # --- BOTÓN GENERAR CON INDICADORES DE CARGA ---
    if st.button("🚀 GENERAR MALLA 2+2"):
        with st.status("Iniciando motor de optimización...", expanded=True) as status:
            
            st.write("🔍 Filtrando personal y analizando contratos (Vie/Sab/Dom)...")
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            progress_bar = st.progress(0)
            
            # Definición del problema
            st.write("🏗️ Construyendo modelo matemático de restricciones...")
            prob = LpProblem("MovilGo_Pro_2_2", LpMaximize)
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            mantiene = LpVariable.dicts("Mantiene", (nombres, range(2, num_dias + 1), LISTA_TURNOS), cat='Binary')
            noche_sem = LpVariable.dicts("NocheSem", (nombres, semanas_mes), cat='Binary')
            
            progress_bar.progress(20)

            # Función Objetivo: Maximizar asignación y estabilidad
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS]) + \
                    lpSum([mantiene[e][d][t] for e in nombres for d in range(2, num_dias + 1) for t in LISTA_TURNOS]) * peso_estabilidad

            # Restricciones
            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                desc_val = str(row['descanso_ley']).lower()
                
                # Clasificación de contrato por empleado
                if "vie" in desc_val: dia_l_pref = "Vie"
                elif "sab" in desc_val: dia_l_pref = "Sab"
                else: dia_l_pref = "Dom"
                
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
                
                # Aplicar 2 descansos obligatorios en su día de contrato
                d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_l_pref]
                prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)
                prob += lpSum([asig[e][d][t] for d in dias_range for t in LISTA_TURNOS]) >= 18 

            progress_bar.progress(50)
            st.write("🧠 Resolviendo matriz operativa (PULP_CBC)...")
            prob.solve(PULP_CBC_CMD(msg=0))
            
            if LpStatus[prob.status] == 'Optimal':
                progress_bar.progress(80)
                st.write("✨ Finalizando post-procesamiento de descansos...")
                
                res_list = []
                for di in dias_info:
                    for e in nombres:
                        t_asig = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[e][di["n"]][t]) == 1: t_asig = t
                        res_list.append({
                            "Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], 
                            "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]
                        })
                
                df_res = pd.DataFrame(res_list)
                lista_final = []
                for emp, grupo in df_res.groupby("Empleado"):
                    grupo = grupo.sort_values("Dia").copy()
                    l_val = str(grupo['Ley'].iloc[0]).lower()
                    d_ley = "Vie" if "vie" in l_val else ("Sab" if "sab" in l_val else "Dom")
                    
                    # 1. Asignar DESC. LEY
                    idx_ley = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == d_ley)].head(2).index
                    grupo.loc[idx_ley, 'Turno'] = 'DESC. LEY'
                    
                    # 2. Asignar COMPENSATORIOS (Evitando Vie/Sab/Dom)
                    t_ley = grupo[(grupo['Nom_Dia'] == d_ley) & (grupo['Turno'].isin(LISTA_TURNOS))]
                    for _, r in t_ley.iterrows():
                        h = grupo[(grupo['Dia'] > r['Dia']) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1)
                        if not h.empty: grupo.loc[h.index, 'Turno'] = 'DESC. COMPENSATORIO'

                    # 3. Post-Noche
                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                            grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                    
                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                progress_bar.progress(100)
                status.update(label="✅ Malla generada satisfactoriamente", state="complete", expanded=False)
            else:
                status.update(label="❌ Error: Sin solución óptima", state="error")
                st.error("No se pudo generar la malla con los cupos actuales. Intenta aumentar el 'Cupo máximo'.")

    # --- 6. VISUALIZACIÓN DE RESULTADOS ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        st.subheader("📊 Resumen de Control")
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Ley</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. LEY'])}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Compensatorios</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DESC. COMPENSATORIO'])}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='metric-card'><div class='metric-title'>Disponibilidad</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'DISPONIBILIDAD'])}</div></div>", unsafe_allow_html=True)
        with c4: st.markdown(f"<div class='metric-card'><div class='metric-title'>Turnos Noche</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'Noche'])}</div></div>", unsafe_allow_html=True)

        t_malla, t_audit, t_repo = st.tabs(["📅 Malla Operativa", "⚖️ Auditoría Legal", "📥 Reportes"])

        with t_malla:
            def color_turnos(v):
                colors = {
                    'DESC. LEY': 'background-color: #fecaca; color: #991b1b; font-weight: bold',
                    'DESC. COMPENSATORIO': 'background-color: #fef08a; color: #854d0e; font-weight: bold',
                    'DESC. POST-NOCHE': 'background-color: #dcfce7; color: #166534; font-weight: bold',
                    'DISPONIBILIDAD': 'color: #3b82f6',
                    'Noche': 'background-color: #1e293b; color: white; font-weight: bold'
                }
                return colors.get(v, 'color: #1e293b')
            
            m_pivot = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            cols_ord = sorted(m_pivot.columns, key=lambda x: int(x.split(' - ')[0]))
            st.dataframe(m_pivot[cols_ord].style.map(color_turnos), use_container_width=True)

        with t_audit:
            audit_data = []
            for e, g in df_v.groupby("Empleado"):
                lv = str(g['Ley'].iloc[0]).lower()
                contrato = "Viernes" if "vie" in lv else ("Sábado" if "sab" in lv else "Domingo")
                audit_data.append({
                    "Empleado": e, "Tipo Contrato": contrato,
                    "D. Ley (Min 2)": len(g[g['Turno'] == 'DESC. LEY']),
                    "Compensatorios": len(g[g['Turno'] == 'DESC. COMPENSATORIO']),
                    "Total Descansos": len(g[g['Turno'].str.contains('DESC')]),
                    "Estado": "✅ OK" if len(g[g['Turno'].str.contains('DESC')]) >= 4 else "⚠️ Revisar"
                })
            st.table(pd.DataFrame(audit_data))

        with t_repo:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                m_pivot[cols_ord].to_excel(writer, sheet_name='Malla_Operativa')
                pd.DataFrame(audit_data).to_excel(writer, sheet_name='Auditoria_Legal', index=False)
            st.download_button("📥 Descargar Excel Final", buf.getvalue(), "Malla_MovilGo_2026.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
