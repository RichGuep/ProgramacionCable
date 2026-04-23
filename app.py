import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import math

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="MovilGo Pro - Gestión de Células", layout="wide", page_icon="🎛️")

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
    # --- 4. PARAMETRIZADOR DE GRUPOS (SIDEBAR) ---
    with st.sidebar:
        st.header("⚙️ Parametrización")
        
        with st.expander("📝 Receta de Célula", expanded=True):
            m_req = st.number_input("Masters", 1, 5, 2)
            ta_req = st.number_input("Técnicos A", 1, 15, 7)
            tb_req = st.number_input("Técnicos B", 1, 10, 3)
        
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes de Programación", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        
        cupo_cel_turno = st.number_input("Células simultáneas", 1, 10, 1)

    # --- LÓGICA DE ARMADO DE CÉLULAS ---
    def armar_celulas_dinamicas(df, m, ta, tb):
        masters = df[df['cargo'].str.contains('Master', case=False, na=False)].copy()
        teca = df[df['cargo'].str.contains('Tecnico A', case=False, na=False)].copy()
        tecb = df[df['cargo'].str.contains('Tecnico B', case=False, na=False)].copy()
        n_g = min(len(masters)//m, len(teca)//ta, len(tecb)//tb)
        
        final_list = []
        for i in range(n_g):
            g_id = f"GRUPO {i+1}"
            for _ in range(m): final_list.append({**masters.iloc[0].to_dict(), "grupo": g_id}); masters = masters.iloc[1:]
            for _ in range(ta): final_list.append({**teca.iloc[0].to_dict(), "grupo": g_id}); teca = teca.iloc[1:]
            for _ in range(tb): final_list.append({**tecb.iloc[0].to_dict(), "grupo": g_id}); tecb = tecb.iloc[1:]
        return pd.DataFrame(final_list), n_g

    df_celulas, total_g = armar_celulas_dinamicas(df_raw, m_req, ta_req, tb_req)

    # --- 5. SELECTOR DE DESCANSOS POR GRUPO ---
    st.title(f"🚀 Programación Operativa: {mes_sel}")
    
    st.subheader("🛠️ Definición de Descansos por Grupo")
    col_g = st.columns(total_g if total_g > 0 else 1)
    dict_descansos = {}
    for i, g_name in enumerate(df_celulas['grupo'].unique()):
        with col_g[i]:
            dict_descansos[g_name] = st.selectbox(f"Ley {g_name}", ["Viernes", "Sabado", "Domingo"], index=i%3)

    # --- 6. MOTOR DE OPTIMIZACIÓN SEMANAL ---
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("⚡ GENERAR MALLA CON ESTABILIDAD SEMANAL"):
        with st.status("Aplicando reglas de estabilidad y leyes...", expanded=True) as status:
            nombres_g = df_celulas['grupo'].unique().tolist()
            prob = LpProblem("MovilGo_Semanal", LpMaximize)
            
            # Variables: El turno se asigna por SEMANA y por GRUPO
            # asig_sem[Grupo][Semana][Turno]
            asig_sem = LpVariable.dicts("AsigSem", (nombres_g, semanas_mes, ["AM", "PM", "Noche"]), cat='Binary')
            
            # Objetivo: Cubrir todos los grupos
            prob += lpSum([asig_sem[g][s][t] for g in nombres_g for s in semanas_mes for t in ["AM", "PM", "Noche"]])

            for s in semanas_mes:
                for t in ["AM", "PM", "Noche"]:
                    # Cobertura por semana
                    prob += lpSum([asig_sem[g][s][t] for g in nombres_g]) <= cupo_cel_turno
                
                for g in nombres_g:
                    # Un solo turno por semana por grupo
                    prob += lpSum([asig_sem[g][s][t] for t in ["AM", "PM", "Noche"]]) <= 1

            # Evitar Noche -> AM la siguiente semana
            for g in nombres_g:
                for i in range(len(semanas_mes)-1):
                    prob += asig_sem[g][semanas_mes[i]]["Noche"] + asig_sem[g][semanas_mes[i+1]]["AM"] <= 1

            prob.solve(PULP_CBC_CMD(msg=0))

            # --- PROCESAMIENTO DE RESULTADOS ---
            res_list = []
            for d_i in dias_info:
                for g in nombres_g:
                    turno_asignado = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig_sem[g][d_i["semana"]][t]) == 1:
                            turno_asignado = t
                    
                    # Regla de Descanso de Ley
                    dia_ley_g = dict_descansos[g][:3] # Vie, Sab, Dom
                    if d_i["nombre"] == dia_ley_g:
                        # Si el motor le asignó turno, lo convertiremos en compensatorio después
                        pass 

                    miembros = df_celulas[df_celulas['grupo'] == g]
                    for _, m in miembros.iterrows():
                        res_list.append({
                            "Dia": d_i["n"], "Label": d_i["label"], "Nom_Dia": d_i["nombre"], 
                            "Semana": d_i["semana"], "Empleado": m['nombre'], "Grupo": g,
                            "Turno_Base": turno_asignado, "Dia_Ley": dict_descansos[g]
                        })

            df_res = pd.DataFrame(res_list)
            
            # --- LÓGICA DE COMPENSATORIOS 1:1 ---
            final_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                d_ley = g_emp['Dia_Ley'].iloc[0][:3]
                
                for s in semanas_mes:
                    f_sem = g_emp[g_emp['Semana'] == s]
                    idx_ley = f_sem[f_sem['Nom_Dia'] == d_ley].index
                    
                    # 1. ¿Le toca descansar por Ley? (Por ahora 2 veces al mes para que rote)
                    # En este modelo simplificado, si trabajó el día de ley, buscamos el lunes siguiente.
                    turno_actual = g_emp.loc[idx_ley, 'Turno_Base'].values[0]
                    
                    if turno_actual != "---":
                        # TRABAJÓ EN SU LEY -> GENERAR COMPENSATORIO (Lunes o Martes siguiente)
                        g_emp.loc[idx_ley, 'Final_Turno'] = turno_actual
                        # Buscar hueco en semana s+1
                        idx_comp = g_emp[(g_emp['Semana'] == s + 1) & (g_emp['Nom_Dia'].isin(['Lun', 'Mar']))].head(1).index
                        if not idx_comp.empty:
                            g_emp.loc[idx_comp, 'Final_Turno'] = "DESC. COMPENSATORIO"
                    else:
                        g_emp.loc[idx_ley, 'Final_Turno'] = "DESC. LEY"
                
                g_emp['Final_Turno'] = g_emp['Final_Turno'].fillna(g_emp['Turno_Base'])
                g_emp.loc[g_emp['Final_Turno'] == '---', 'Final_Turno'] = 'DISPONIBILIDAD'
                final_rows.append(g_emp)

            st.session_state['malla_grupos'] = pd.concat(final_rows)
            status.update(label="✅ Malla con estabilidad semanal generada.", state="complete")

    # --- 7. VISTAS Y FILTROS ---
    if 'malla_grupos' in st.session_state:
        tab_malla, tab_auditoria = st.tabs(["📅 Malla y Filtros", "⚖️ Auditoría Legal"])
        
        with tab_malla:
            col_f1, col_f2 = st.columns(2)
            f_grupo = col_f1.multiselect("Filtrar por Grupo", st.session_state['malla_grupos']['Grupo'].unique())
            f_emp = col_f2.text_input("Buscar Empleado")
            
            df_display = st.session_state['malla_grupos'].copy()
            if f_grupo: df_display = df_display[df_display['Grupo'].isin(f_grupo)]
            if f_emp: df_display = df_display[df_display['Empleado'].str.contains(f_emp, case=False)]
            
            pivote = df_display.pivot(index=['Grupo', 'Empleado'], columns='Label', values='Final_Turno')
            
            def color_malla(val):
                if 'LEY' in str(val): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMP' in str(val): return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if val == 'Noche': return 'background-color: #1e293b; color: white'
                return ''
            
            st.dataframe(pivote.style.map(color_malla), use_container_width=True)

        with tab_auditoria:
            st.subheader("Auditoría de Descansos Semanales")
            audit_data = []
            for emp, data in st.session_state['malla_grupos'].groupby("Empleado"):
                ley = len(data[data['Final_Turno'] == 'DESC. LEY'])
                comp = len(data[data['Final_Turno'] == 'DESC. COMPENSATORIO'])
                audit_data.append({
                    "Empleado": emp,
                    "Grupo": data['Grupo'].iloc[0],
                    "Día Ley Asignado": data['Dia_Ley'].iloc[0],
                    "Días Ley Tomados": ley,
                    "Compensatorios": comp,
                    "Total Descansos": ley + comp,
                    "Estatus": "✅ CUMPLE" if (ley+comp) >= len(semanas_mes) else "⚠️ REVISAR"
                })
            st.table(pd.DataFrame(audit_data))
