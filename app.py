import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import math

# --- 1. CONFIGURACIÓN Y VARIABLES GLOBALES ---
st.set_page_config(page_title="MovilGo Pro - Control de Células", layout="wide", page_icon="🎛️")

LISTA_TURNOS = ["AM", "PM", "Noche"]

st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f4f7f9; }
    .status-card { background-color: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid #1e293b; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo Control Panel</h1>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True; st.rerun()
                else: st.error("Acceso denegado")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except: return None

df_raw = load_base()

if df_raw is not None:
    # --- 4. PARAMETRIZADOR (SIDEBAR) ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        with st.expander("📝 Receta de Célula", expanded=True):
            m_req = st.number_input("Masters", 1, 5, 2)
            ta_req = st.number_input("Técnicos A", 1, 15, 7)
            tb_req = st.number_input("Técnicos B", 1, 10, 3)
        
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        
        cupo_cel_turno = st.number_input("Células por turno", 1, 10, 1)

    def armar_celulas(df, m, ta, tb):
        masters = df[df['cargo'].str.contains('Master', case=False, na=False)].copy()
        teca = df[df['cargo'].str.contains('Tecnico A', case=False, na=False)].copy()
        tecb = df[df['cargo'].str.contains('Tecnico B', case=False, na=False)].copy()
        n_g = min(len(masters)//m if m>0 else 99, len(teca)//ta if ta>0 else 99, len(tecb)//tb if tb>0 else 99)
        
        final_list = []
        for i in range(n_g):
            g_id = f"GRUPO {i+1}"
            for _ in range(m): final_list.append({**masters.iloc[0].to_dict(), "grupo": g_id}); masters = masters.iloc[1:]
            for _ in range(ta): final_list.append({**teca.iloc[0].to_dict(), "grupo": g_id}); teca = teca.iloc[1:]
            for _ in range(tb): final_list.append({**tecb.iloc[0].to_dict(), "grupo": g_id}); tecb = tecb.iloc[1:]
        return pd.DataFrame(final_list), n_g

    df_celulas, total_g = armar_celulas(df_raw, m_req, ta_req, tb_req)

    # --- 5. SELECTOR DE DESCANSOS EXCLUSIVOS ---
    st.title(f"🚀 Control Operativo - {mes_sel}")
    st.subheader("📅 Asignación de Días de Ley (Exclusivos)")
    
    opciones_descanso = ["Lunes", "Viernes", "Sabado", "Domingo"]
    dict_descansos = {}
    nombres_grupos = df_celulas['grupo'].unique()
    
    cols = st.columns(max(total_g, 1))
    for i, g_name in enumerate(nombres_grupos):
        with cols[i]:
            dict_descansos[g_name] = st.selectbox(f"Ley {g_name}", opciones_descanso, index=i % len(opciones_descanso))

    # --- VALIDACIÓN DE EXCLUSIVIDAD ---
    valores_seleccionados = list(dict_descansos.values())
    if len(valores_seleccionados) != len(set(valores_seleccionados)):
        st.warning("⚠️ Hay grupos compartiendo el mismo día de descanso. Se recomienda exclusividad para no dejar la planta sola.")

    # --- 6. MOTOR DE OPTIMIZACIÓN ---
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("⚡ GENERAR MALLA SIN SOLAPAMIENTO"):
        with st.status("Optimizando flujos de trabajo...", expanded=True) as status:
            prob = LpProblem("MovilGo_Sync", LpMaximize)
            asig_sem = LpVariable.dicts("AsigSem", (nombres_grupos, semanas_mes, LISTA_TURNOS), cat='Binary')
            
            # Maximizar asignación
            prob += lpSum([asig_sem[g][s][t] for g in nombres_grupos for s in semanas_mes for t in LISTA_TURNOS])

            for s in semanas_mes:
                for t in LISTA_TURNOS:
                    # Garantizar que siempre haya cobertura (mínimo de células trabajando)
                    prob += lpSum([asig_sem[g][s][t] for g in nombres_grupos]) <= cupo_cel_turno
                
                for g in nombres_grupos:
                    prob += lpSum([asig_sem[g][s][t] for t in LISTA_TURNOS]) <= 1

            # Regla de Estabilidad y No-Retorno
            for g in nombres_grupos:
                for i in range(len(semanas_mes)-1):
                    prob += asig_sem[g][semanas_mes[i]]["Noche"] + asig_sem[g][semanas_mes[i+1]]["AM"] <= 0
                    prob += asig_sem[g][semanas_mes[i]]["Noche"] + asig_sem[g][semanas_mes[i+1]]["PM"] <= 0

            prob.solve(PULP_CBC_CMD(msg=0))

            # --- PROCESAMIENTO CON LÓGICA DE SALIDA DE NOCHE ---
            res_list = []
            for d_i in dias_info:
                for g in nombres_grupos:
                    t_base = "---"
                    for t in LISTA_TURNOS:
                        if value(asig_sem[g][d_i["semana"]][t]) == 1:
                            t_base = t
                    
                    miembros = df_celulas[df_celulas['grupo'] == g]
                    for _, m in miembros.iterrows():
                        res_list.append({
                            "Dia": d_i["n"], "Label": d_i["label"], "Nom_Dia": d_i["nombre"], 
                            "Semana": d_i["semana"], "Empleado": m['nombre'], "Grupo": g,
                            "Turno_Base": t_base, "Dia_Ley": dict_descansos[g]
                        })

            df_res = pd.DataFrame(res_list)
            final_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                dl_pref = g_emp['Dia_Ley'].iloc[0][:3]
                
                for s in semanas_mes:
                    f_sem = g_emp[g_emp['Semana'] == s]
                    idx_l = f_sem[f_sem['Nom_Dia'] == dl_pref].index
                    turno_w = g_emp.loc[idx_l, 'Turno_Base'].values[0] if not idx_l.empty else "---"
                    
                    if turno_w == "Noche":
                        # PRIORIDAD: Si es semana de noche, el descanso se mueve al final 
                        # para no romper el ciclo nocturno (usualmente Domingo o Lunes)
                        g_emp.loc[idx_l, 'Turno_Final'] = "Noche"
                        # Buscamos el día de descanso compensatorio al final de la jornada de noche
                        idx_c = g_emp[(g_emp['Semana'] == s) & (g_emp['Nom_Dia'].isin(['Dom', 'Lun']))].tail(1).index
                        if not idx_c.empty: g_emp.loc[idx_c, 'Turno_Final'] = "DESC. POST-NOCHE"
                    elif turno_w != "---":
                        # Semana normal: Si trabajó su ley, compensa entre semana
                        g_emp.loc[idx_l, 'Turno_Final'] = turno_w
                        idx_comp = g_emp[(g_emp['Semana'] == s) & (g_emp['Nom_Dia'].isin(['Mar', 'Mie', 'Jue']))].head(1).index
                        if not idx_comp.empty: g_emp.loc[idx_comp, 'Turno_Final'] = "DESC. COMPENSATORIO"
                    else:
                        if not idx_l.empty: g_emp.loc[idx_l, 'Turno_Final'] = "DESC. LEY"
                
                g_emp['Turno_Final'] = g_emp['Turno_Final'].fillna(g_emp['Turno_Base'])
                g_emp.loc[g_emp['Turno_Final'] == '---', 'Turno_Final'] = 'DISPONIBILIDAD'
                final_rows.append(g_emp)

            st.session_state['malla_final'] = pd.concat(final_rows)
            status.update(label="✅ Malla sincronizada y optimizada.", state="complete")

    # --- 7. VISTAS ---
    if 'malla_final' in st.session_state:
        tab1, tab2 = st.tabs(["📅 Malla", "⚖️ Auditoría"])
        with tab1:
            df_v = st.session_state['malla_final']
            pivote = df_v.pivot(index=['Grupo', 'Empleado'], columns='Label', values='Turno_Final')
            cols_ord = sorted(pivote.columns, key=lambda x: int(x.split('-')[0]))
            
            def styler(v):
                if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMP' in str(v) or 'POST' in str(v): return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if v == 'Noche': return 'background-color: #1e293b; color: white'
                return ''
            st.dataframe(pivote[cols_ord].style.map(styler), use_container_width=True)

        with tab2:
            audit = []
            for emp, data in st.session_state['malla_final'].groupby("Empleado"):
                total = len(data[data['Turno_Final'].str.contains('DESC')])
                audit.append({"Empleado": emp, "Grupo": data['Grupo'].iloc[0], "Descansos": total, "Semanas": len(semanas_mes)})
            st.table(pd.DataFrame(audit))
