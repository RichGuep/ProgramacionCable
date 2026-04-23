import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import math

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Sistema de Células", layout="wide", page_icon="⚙️")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    .group-box { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #1e293b; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<h1 style='text-align:center;'>MovilGo Admin</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. MOTOR DE DATOS Y AGRUPAMIENTO ---
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
    with st.sidebar:
        st.header("🛠️ Parametrizador de Células")
        
        with st.expander("Composición de Célula", expanded=True):
            m_req = st.number_input("Masters por Grupo", 1, 5, 2)
            ta_req = st.number_input("Técnicos A por Grupo", 1, 15, 7)
            tb_req = st.number_input("Técnicos B por Grupo", 1, 10, 3)
        
        st.divider()
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        cupo_grupos = st.number_input("Células por Turno", 1, 10, 1)

    # --- LÓGICA DE ARMADO DE GRUPOS ---
    def armar_celulas(df, m, ta, tb):
        masters = df[df['cargo'].str.contains('Master', case=False, na=False)].copy()
        teca = df[df['cargo'].str.contains('Tecnico A', case=False, na=False)].copy()
        tecb = df[df['cargo'].str.contains('Tecnico B', case=False, na=False)].copy()
        
        num_posibles = min(len(masters)//m if m > 0 else 999, 
                           len(teca)//ta if ta > 0 else 999, 
                           len(tecb)//tb if tb > 0 else 999)
        
        celulas = []
        for i in range(num_posibles):
            g_id = f"Célula {i+1}"
            dia_ley = ["Viernes", "Sabado", "Domingo"][i % 3]
            for _ in range(m): 
                celulas.append({**masters.iloc[0].to_dict(), "grupo": g_id, "ley_grupo": dia_ley})
                masters = masters.iloc[1:]
            for _ in range(ta): 
                celulas.append({**teca.iloc[0].to_dict(), "grupo": g_id, "ley_grupo": dia_ley})
                teca = teca.iloc[1:]
            for _ in range(tb): 
                celulas.append({**tecb.iloc[0].to_dict(), "grupo": g_id, "ley_grupo": dia_ley})
                tecb = tecb.iloc[1:]
        return pd.DataFrame(celulas), num_posibles

    df_celulas, n_grupos = armar_celulas(df_raw, m_req, ta_req, tb_req)

    # Fechas
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("🚀 GENERAR MALLA POR CÉLULAS"):
        if n_grupos == 0:
            st.error("Personal insuficiente para armar la célula.")
        else:
            with st.status("Optimizando...", expanded=True) as status:
                nombres_g = df_celulas['grupo'].unique().tolist()
                prob = LpProblem("Malla_Final", LpMaximize)
                asig = LpVariable.dicts("AsigG", (nombres_g, dias_range, LISTA_TURNOS), cat='Binary')
                
                prob += lpSum([asig[g][d][t] for g in nombres_g for d in dias_range for t in LISTA_TURNOS])

                for d in dias_range:
                    for t in LISTA_TURNOS:
                        prob += lpSum([asig[g][d][t] for g in nombres_g]) <= cupo_grupos

                for g in nombres_g:
                    dl_pref = df_celulas[df_celulas['grupo'] == g]['ley_grupo'].iloc[0][:3]
                    for d in dias_range:
                        prob += lpSum([asig[g][d][t] for t in LISTA_TURNOS]) <= 1
                        if d < num_dias:
                            prob += asig[g][d]["Noche"] + asig[g][d+1]["AM"] <= 1
                    
                    for sem in semanas_mes:
                        d_sem = [di["n"] for di in dias_info if di["semana"] == sem]
                        prob += lpSum([asig[g][d][t] for d in d_sem for t in LISTA_TURNOS]) <= (len(d_sem) - 1)

                prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

                if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                    res_final = []
                    for di in dias_info:
                        for g in nombres_g:
                            t_asig = "---"
                            for t in LISTA_TURNOS:
                                if value(asig[g][di["n"]][t]) == 1: t_asig = t
                            
                            m_cel = df_celulas[df_celulas['grupo'] == g]
                            for _, m in m_cel.iterrows():
                                res_final.append({
                                    "Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], 
                                    "Semana": di["semana"], "Empleado": m['nombre'], "Grupo": g,
                                    "Turno": t_asig, "Contrato": m['ley_grupo']
                                })
                    
                    df_res = pd.DataFrame(res_final)
                    lista_p = []
                    for _, g_emp in df_res.groupby("Empleado"):
                        g_emp = g_emp.sort_values("Dia").copy()
                        dl = g_emp['Contrato'].iloc[0][:3]
                        for s in semanas_mes:
                            f_sem = g_emp[g_emp['Semana'] == s]
                            dia_l_sem = f_sem[f_sem['Nom_Dia'] == dl]
                            if not dia_l_sem.empty:
                                if dia_l_sem['Turno'].iloc[0] in LISTA_TURNOS:
                                    idx_c = g_emp[(g_emp['Semana'] == s + 1) & (g_emp['Turno'] == '---') & (~g_emp['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1).index
                                    if not idx_c.empty: g_emp.loc[idx_c, 'Turno'] = 'DESC. COMPENSATORIO'
                                else:
                                    g_emp.loc[dia_l_sem.index, 'Turno'] = 'DESC. LEY'
                        g_emp.loc[g_emp['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                        lista_p.append(g_emp)

                    st.session_state['df_final'] = pd.concat(lista_p)
                    status.update(label="✅ Malla generada.", state="complete", expanded=False)

    # --- VISTAS ---
    if 'df_final' in st.session_state:
        t_malla, t_grupos = st.tabs(["📅 Malla Operativa", "👥 Grupos"])
        
        with t_malla:
            df_v = st.session_state['df_final']
            m_piv = df_v.pivot(index=['Grupo', 'Empleado'], columns='Label', values='Turno')
            
            # Ordenar columnas por día numérico
            cols_ord = sorted(m_piv.columns, key=lambda x: int(x.split('-')[0]))
            m_piv = m_piv[cols_ord]

            # FUNCIÓN DE ESTILO ACTUALIZADA (map en vez de applymap)
            def color_turnos(v):
                if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMP' in str(v): return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                return ''

            st.dataframe(m_piv.style.map(color_turnos), use_container_width=True)
            
        with t_grupos:
            st.write(f"### Total Células: {n_grupos}")
            st.dataframe(df_celulas[['grupo', 'nombre', 'cargo', 'ley_grupo']], use_container_width=True)
