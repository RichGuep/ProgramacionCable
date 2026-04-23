import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import math

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Ciclo Noche-PM-AM", layout="wide", page_icon="⚙️")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo Control</h1>", unsafe_allow_html=True)
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
    with st.sidebar:
        st.header("⚙️ Parametrización")
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

    st.title(f"🚀 Malla Operativa Ciclo Noche-PM-AM: {mes_sel}")
    
    # Selector de descansos exclusivos
    opciones_descanso = ["Lunes", "Viernes", "Sabado", "Domingo"]
    dict_descansos = {}
    nombres_grupos = df_celulas['grupo'].unique()
    cols = st.columns(max(total_g, 1))
    for i, g_name in enumerate(nombres_grupos):
        with cols[i]:
            dict_descansos[g_name] = st.selectbox(f"Ley {g_name}", opciones_descanso, index=i % len(opciones_descanso))

    # Fechas
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("⚡ GENERAR MALLA DE COBERTURA TOTAL"):
        with st.status("Aplicando ciclo de rotación Noche-PM-AM...", expanded=True) as status:
            prob = LpProblem("MovilGo_Cobertura", LpMaximize)
            asig_sem = LpVariable.dicts("AsigSem", (nombres_grupos, semanas_mes, LISTA_TURNOS), cat='Binary')
            
            # --- FUNCIÓN OBJETIVO: Prioridad absoluta a llenar los turnos ---
            prob += lpSum([asig_sem[g][s][t] * 100 for g in nombres_grupos for s in semanas_mes for t in LISTA_TURNOS])

            for s in semanas_mes:
                for t in LISTA_TURNOS:
                    # Garantizar que los turnos estén cubiertos según el cupo
                    prob += lpSum([asig_sem[g][s][t] for g in nombres_grupos]) == cupo_cel_turno
                
                for g in nombres_grupos:
                    # Cada grupo debe tener un turno asignado por semana
                    prob += lpSum([asig_sem[g][s][t] for t in LISTA_TURNOS]) == 1

            # --- REGLA DE CICLO: Noche -> PM -> AM ---
            for g in nombres_grupos:
                for i in range(len(semanas_mes)-1):
                    s_act = semanas_mes[i]
                    s_sig = semanas_mes[i+1]
                    # Si es Noche, la que sigue es PM
                    prob += asig_sem[g][s_act]["Noche"] <= asig_sem[g][s_sig]["PM"]
                    # Si es PM, la que sigue es AM
                    prob += asig_sem[g][s_act]["PM"] <= asig_sem[g][s_sig]["AM"]
                    # Si es AM, la que sigue es Noche
                    prob += asig_sem[g][s_act]["AM"] <= asig_sem[g][s_sig]["Noche"]

            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

            # --- PROCESAMIENTO ---
            res_list = []
            for d_i in dias_info:
                for g in nombres_grupos:
                    t_final = "---"
                    for t in LISTA_TURNOS:
                        if value(asig_sem[g][d_i["semana"]][t]) == 1:
                            t_final = t
                    
                    # Identificar si es su día de descanso de ley
                    es_descanso = False
                    dl_g = dict_descansos[g][:3]
                    if d_i["nombre"] == dl_g:
                        es_descanso = True

                    miembros = df_celulas[df_celulas['grupo'] == g]
                    for _, m in miembros.iterrows():
                        res_list.append({
                            "Dia": d_i["n"], "Label": d_i["label"], "Nom_Dia": d_i["nombre"], 
                            "Semana": d_i["semana"], "Empleado": m['nombre'], "Grupo": g,
                            "Turno_Asig": t_final, "Es_Ley": es_descanso, "Dia_Ley": dict_descansos[g]
                        })

            df_res = pd.DataFrame(res_list)
            final_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                
                for s in semanas_mes:
                    f_sem = g_emp[g_emp['Semana'] == s]
                    t_sem = f_sem['Turno_Asig'].iloc[0]
                    
                    # Lógica de descansos:
                    if t_sem == "Noche":
                        # Salida de Noche: El descanso de ley se mueve al final de la semana (Dom o Lun)
                        g_emp.loc[f_sem.index, 'Resultado'] = "Noche"
                        idx_desc = f_sem[f_sem['Nom_Dia'].isin(['Dom', 'Lun'])].tail(1).index
                        g_emp.loc[idx_desc, 'Resultado'] = "DESC. POST-NOCHE"
                    else:
                        # Semanas AM o PM: Descansa en su día de contrato
                        g_emp.loc[f_sem.index, 'Resultado'] = t_sem
                        idx_ley = f_sem[f_sem['Es_Ley'] == True].index
                        if not idx_ley.empty:
                            g_emp.loc[idx_ley, 'Resultado'] = "DESC. LEY"
                        else:
                            # Si su día de ley no está en esta semana (meses partidos), compensatorio
                            idx_comp = f_sem[f_sem['Nom_Dia'] == 'Lun'].index
                            g_emp.loc[idx_comp, 'Resultado'] = "DESC. COMPENSATORIO"

                final_rows.append(g_emp)

            st.session_state['malla_ciclo'] = pd.concat(final_rows)
            status.update(label="✅ Malla generada con ciclo Noche-PM-AM.", state="complete")

    # --- 7. VISTAS ---
    if 'malla_ciclo' in st.session_state:
        df_v = st.session_state['malla_ciclo']
        pivote = df_v.pivot(index=['Grupo', 'Empleado'], columns='Label', values='Resultado')
        cols_ord = sorted(pivote.columns, key=lambda x: int(x.split('-')[0]))
        
        def styler(v):
            if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
            if 'COMP' in str(v) or 'POST' in str(v): return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
            if v == 'Noche': return 'background-color: #1e293b; color: white'
            if v == 'PM': return 'background-color: #e0f2fe; color: #0369a1'
            if v == 'AM': return 'background-color: #dcfce7; color: #166534'
            return ''
            
        st.dataframe(pivote[cols_ord].style.map(styler), use_container_width=True)
