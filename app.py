import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Sistema Universal", layout="wide", page_icon="⚡")
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

# --- 4. MOTOR DE DATOS ---
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
        st.header("⚙️ Panel de Control")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        cargo_sel = st.selectbox("Seleccionar Cargo", sorted(df_raw['cargo'].unique()))
        cupo_manual = st.number_input("Personal por Turno", 1, 20, 2)
        
        st.divider()
        st.info("💡 Para grupos pequeños (Masters), mantenga el cupo en 2. Para operativos grandes, suba el cupo según necesidad.")

    # Preparación de fechas
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button(f"🚀 GENERAR MALLA: {cargo_sel.upper()}"):
        with st.status(f"Procesando {cargo_sel}...", expanded=True) as status:
            
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            nombres = df_f['nombre'].tolist()
            prog = st.progress(0)
            
            # --- MODELO MATEMÁTICO OPTIMIZADO ---
            prob = LpProblem("Malla_Universal", LpMaximize)
            asig = LpVariable.dicts("Asig", (nombres, dias_range, LISTA_TURNOS), cat='Binary')
            
            # Objetivo: Llenar la mayor cantidad de turnos posibles
            prob += lpSum([asig[e][d][t] for e in nombres for d in dias_range for t in LISTA_TURNOS])
            
            # Restricciones
            for d in dias_range:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in nombres]) <= cupo_manual

            for e in nombres:
                row = df_f[df_f['nombre'] == e].iloc[0]
                d_val = str(row['descanso_ley']).lower()
                # Detección dinámica de contrato
                dia_l = "Vie" if "vie" in d_val else ("Sab" if "sab" in d_val else "Dom")
                
                for d in dias_range:
                    prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1 # Solo 1 turno al día
                    if d < num_dias:
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1 # Descanso post-noche mínimo
                
                # Garantizar espacio para 2 descansos de ley
                d_ley_m = [di["n"] for di in dias_info if di["nombre"] == dia_l]
                prob += lpSum([asig[e][d][t] for d in d_ley_m for t in LISTA_TURNOS]) <= (len(d_ley_m) - 2)

            prog.progress(40)
            st.write("🧠 Calculando combinaciones óptimas...")
            
            # AJUSTES DE VELOCIDAD CRÍTICOS:
            # timeLimit=20 (Max 20 seg), gapRel=0.1 (Termina al estar 90% seguro)
            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=20, gapRel=0.1, threads=4))
            
            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                prog.progress(70)
                st.write("⚙️ Asignando descansos y compensatorios...")
                
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
                    lv = str(grupo['Ley'].iloc[0]).lower()
                    dl = "Vie" if "vie" in lv else ("Sab" if "sab" in lv else "Dom")
                    
                    # 1. Marcar Descansos de Ley
                    idx_ley = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dl)].head(2).index
                    grupo.loc[idx_ley, 'Turno'] = 'DESC. LEY'
                    
                    # 2. Marcar Compensatorios (si trabajó en día de ley)
                    trabajo_ley = grupo[(grupo['Nom_Dia'] == dl) & (grupo['Turno'].isin(LISTA_TURNOS))]
                    for _, r in trabajo_ley.iterrows():
                        h = grupo[(grupo['Dia'] > r['Dia']) & (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1)
                        if not h.empty: grupo.loc[h.index, 'Turno'] = 'DESC. COMPENSATORIO'

                    # 3. Post-Noche visual
                    for i in range(len(grupo)-1):
                        if grupo.iloc[i]['Turno'] == 'Noche' and grupo.iloc[i+1]['Turno'] == '---':
                            grupo.iloc[i+1, grupo.columns.get_loc('Turno')] = 'DESC. POST-NOCHE'
                    
                    grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_final.append(grupo)
                
                st.session_state['df_final'] = pd.concat(lista_final)
                prog.progress(100)
                status.update(label="✅ Malla generada con éxito", state="complete", expanded=False)
            else:
                st.error("No se encontró solución. Intente subir el 'Personal por Turno'.")

    # --- VISUALIZACIÓN ---
    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        # Resumen Rápido
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-title'>Total Personal</div><div class='metric-val'>{len(df_v['Empleado'].unique())}</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-title'>Descansos Programados</div><div class='metric-val'>{len(df_v[df_v['Turno'].str.contains('DESC')])}</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='metric-card'><div class='metric-title'>Turnos Noche</div><div class='metric-val'>{len(df_v[df_v['Turno'] == 'Noche'])}</div></div>", unsafe_allow_html=True)

        tab_m, tab_a, tab_r = st.tabs(["📅 Vista de Malla", "⚖️ Auditoría de Ley", "📥 Descargas"])

        with tab_m:
            def estilo_celda(v):
                if v == 'DESC. LEY': return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if v == 'DESC. COMPENSATORIO': return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if 'POST-NOCHE' in v: return 'background-color: #dcfce7; color: #166534'
                if v == 'Noche': return 'background-color: #1e293b; color: white; font-weight: bold'
                if v == 'DISPONIBILIDAD': return 'color: #3b82f6'
                return 'color: #1e293b'

            m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
            # Ordenar columnas por el número del día
            cols_sorted = sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))
            st.dataframe(m_piv[cols_sorted].style.map(estilo_celda), use_container_width=True)

        with tab_a:
            audit = []
            for e, g in df_v.groupby("Empleado"):
                lv = str(g['Ley'].iloc[0]).lower()
                contrato = "Viernes" if "vie" in lv else ("Sábado" if "sab" in lv else "Domingo")
                total_d = len(g[g['Turno'].str.contains('DESC')])
                audit.append({
                    "Empleado": e, "Contrato": contrato,
                    "Descansos Totales": total_d,
                    "Estado": "✅ CUMPLE" if total_d >= 4 else "⚠️ REVISAR"
                })
            st.table(pd.DataFrame(audit))

        with tab_r:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                m_piv[cols_sorted].to_excel(writer, sheet_name='Malla')
            st.download_button("📥 Descargar Excel", buf.getvalue(), f"Malla_{cargo_sel}_{mes_sel}.xlsx")
