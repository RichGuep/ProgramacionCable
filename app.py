import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN Y NOMENCLATURA ---
st.set_page_config(page_title="MovilGo Pro - Gestión de Refuerzos", layout="wide", page_icon="⚙️")
LISTA_TURNOS = ["T1", "T2", "T3"] 

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo Admin</h1>", unsafe_allow_html=True)
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
        st.header("⚙️ Configuración Operativa")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1

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

    st.title(f"📊 Programación con Refuerzos (DISPO): {mes_sel}")
    
    dict_descansos = {}
    nombres_grupos = df_celulas['grupo'].unique()
    cols = st.columns(max(total_g, 1))
    for i, g_name in enumerate(nombres_grupos):
        with cols[i]:
            dict_descansos[g_name] = st.selectbox(f"Ley {g_name}", ["Lunes", "Viernes", "Sabado", "Domingo"], index=i % 4)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("⚡ GENERAR MALLA CON DISTINCIÓN DISPO"):
        with st.status("Identificando grupos de refuerzo...", expanded=True) as status:
            prob = LpProblem("MovilGo_Dispo_Style", LpMaximize)
            asig_sem = LpVariable.dicts("AsigSem", (nombres_grupos, semanas_mes, LISTA_TURNOS), cat='Binary')
            
            prob += lpSum([asig_sem[g][s][t] for g in nombres_grupos for s in semanas_mes for t in LISTA_TURNOS])

            # Seguimiento de qué grupos son "Base" para cada turno/semana
            base_turno = {} 

            for s in semanas_mes:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig_sem[g][s][t] for g in nombres_grupos]) >= 1
                for g in nombres_grupos:
                    prob += lpSum([asig_sem[g][s][t] for t in LISTA_TURNOS]) <= 1

            for g in nombres_grupos:
                for i in range(len(semanas_mes)-1):
                    s_a = semanas_mes[i]; s_s = semanas_mes[i+1]
                    prob += asig_sem[g][s_a]["T3"] <= asig_sem[g][s_s]["T2"]
                    prob += asig_sem[g][s_a]["T2"] <= asig_sem[g][s_s]["T1"]

            prob.solve(PULP_CBC_CMD(msg=0))

            # Identificar el primer grupo asignado como el "Base" para marcar a los demás como DISPO
            res_base_map = {}
            for s in semanas_mes:
                for t in LISTA_TURNOS:
                    encontrado = False
                    for g in nombres_grupos:
                        if value(asig_sem[g][s][t]) == 1 and not encontrado:
                            res_base_map[(g, s)] = t
                            encontrado = True
                        elif value(asig_sem[g][s][t]) == 1 and encontrado:
                            res_base_map[(g, s)] = f"{t} DISPO"

            res_list = []
            for d_i in dias_info:
                for g in nombres_grupos:
                    t_final = res_base_map.get((g, d_i["semana"]), "DISPONIBILIDAD")
                    es_ley = (d_i["nombre"] == dict_descansos[g][:3])
                    miembros = df_celulas[df_celulas['grupo'] == g]
                    for _, m in miembros.iterrows():
                        res_list.append({
                            "Dia": d_i["n"], "Label": d_i["label"], "Nom_Dia": d_i["nombre"], 
                            "Semana": d_i["semana"], "Empleado": m['nombre'], "Grupo": g,
                            "Turno_Base": t_final, "Es_Ley": es_ley, "Contrato": dict_descansos[g]
                        })

            df_res = pd.DataFrame(res_list)
            f_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                for s in semanas_mes:
                    f_sem = g_emp[g_emp['Semana'] == s]
                    t_s = f_sem['Turno_Base'].iloc[0]
                    g_emp.loc[f_sem.index, 'Resultado'] = t_s
                    idx_l = f_sem[f_sem['Es_Ley']].index
                    if not idx_l.empty: g_emp.loc[idx_l, 'Resultado'] = "DESC. LEY"
                f_rows.append(g_emp)

            st.session_state['malla_final'] = pd.concat(f_rows)
            status.update(label="✅ Malla generada con etiquetas DISPO.", state="complete")

    if 'malla_final' in st.session_state:
        tab1, tab2 = st.tabs(["📅 Malla T1-T2-T3 DISPO", "🛡️ Auditoría de Refuerzos"])

        with tab1:
            piv = st.session_state['malla_final'].pivot(index=['Grupo', 'Empleado'], columns='Label', values='Resultado')
            cols = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
            
            def styler(v):
                if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'DISPO' in str(v) and v != 'DISPONIBILIDAD': return 'background-color: #fef9c3; color: #854d0e; border: 1px dashed #ca8a04' # Amarillo Refuerzo
                if v == 'T3': return 'background-color: #1e293b; color: white'
                if v == 'T1': return 'background-color: #dcfce7; color: #166534'
                if v == 'T2': return 'background-color: #e0f2fe; color: #0369a1'
                return 'color: #94a3b8; font-style: italic'
                
            st.dataframe(piv[cols].style.map(styler), use_container_width=True)

        with tab2:
            st.subheader("Análisis de Grupos de Apoyo")
            refuerzos = st.session_state['malla_final'][st.session_state['malla_final']['Resultado'].str.contains('DISPO') & (st.session_state['malla_final']['Resultado'] != 'DISPONIBILIDAD')]
            if not refuerzos.empty:
                st.write("Los siguientes grupos están apoyando turnos fuera de su asignación base:")
                st.table(refuerzos[['Grupo', 'Empleado', 'Semana', 'Resultado']].drop_duplicates())
            else:
                st.info("No hay refuerzos asignados; todos los grupos están en su turno base o disponibilidad pura.")
