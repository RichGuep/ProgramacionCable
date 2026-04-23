import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import io
import math

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Células Operativas", layout="wide", page_icon="👥")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f1f5f9; }
    .group-card { background-color: white; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<h1 style='text-align:center;'>MovilGo Grupos</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Usuario")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.rerun()
                    else: st.error("Credenciales Incorrectas")
        st.stop()

login_page()

# --- 4. CARGA Y CREACIÓN DE GRUPOS ---
@st.cache_data
def load_and_group():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        # Estandarizar nombres de columnas
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        
        # Filtrar por cargos necesarios para las células
        masters = df[df['cargo'].str.contains('Master', case=False, na=False)].copy()
        teca = df[df['cargo'].str.contains('Tecnico A', case=False, na=False)].copy()
        tecb = df[df['cargo'].str.contains('Tecnico B', case=False, na=False)].copy()
        
        # Calcular cuántos grupos completos podemos armar
        num_grupos = min(len(masters)//2, len(teca)//7, len(tecb)//3)
        
        grupos_dict = []
        for i in range(num_grupos):
            g_id = f"Célula {i+1}"
            # Asignar día de ley rotativo para que los grupos se cubran entre sí
            dia_ley = ["Viernes", "Sabado", "Domingo"][i % 3]
            
            # Extraer integrantes
            miembros = []
            for _ in range(2): miembros.append(masters.pop(masters.index[0]))
            for _ in range(7): miembros.append(teca.pop(teca.index[0]))
            for _ in range(3): miembros.append(tecb.pop(tecb.index[0]))
            
            for m in miembros:
                grupos_dict.append({
                    "nombre": m['nombre'],
                    "cargo": m['cargo'],
                    "grupo": g_id,
                    "descanso_ley": dia_ley
                })
        
        return pd.DataFrame(grupos_dict), num_grupos
    except Exception as e:
        st.error(f"Error al procesar grupos: {e}")
        return None, 0

df_grupos, total_g = load_and_group()

if df_grupos is not None:
    with st.sidebar:
        st.header("⚙️ Configuración de Malla")
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        
        st.metric("Total Células Armadas", total_g)
        st.write("*(Cada célula: 2 Master, 7 Tec A, 3 Tec B)*")

    # Fechas
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    dias_info = [{"n": d, "nombre": dias_es[datetime(ano_sel, mes_num, d).weekday()], "semana": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in dias_range]
    semanas_mes = sorted(list(set([d["semana"] for d in dias_info])))

    if st.button("🚀 GENERAR MALLA POR CÉLULAS"):
        with st.status("Optimizando rotación de grupos completos...", expanded=True) as status:
            nombres_g = df_grupos['grupo'].unique().tolist()
            
            prob = LpProblem("Malla_Grupos", LpMaximize)
            asig = LpVariable.dicts("AsigG", (nombres_g, dias_range, LISTA_TURNOS), cat='Binary')
            
            # Maximizar asignación
            prob += lpSum([asig[g][d][t] for g in nombres_g for d in dias_range for t in LISTA_TURNOS])

            for d in dias_range:
                for t in LISTA_TURNOS:
                    # Control de cobertura: cuántas células por turno
                    prob += lpSum([asig[g][d][t] for g in nombres_g]) <= math.ceil(total_g / 3)

            for g in nombres_g:
                dia_l_pref = df_grupos[df_grupos['grupo'] == g]['descanso_ley'].iloc[0][:3] # Vie, Sab, Dom
                
                for d in dias_range:
                    prob += lpSum([asig[g][d][t] for t in LISTA_TURNOS]) <= 1
                    if d < num_dias:
                        prob += asig[g][d]["Noche"] + asig[g][d+1]["AM"] <= 1
                
                # Garantizar que el grupo descanse al menos 2 veces su día de ley
                d_ley_g = [di["n"] for di in dias_info if di["nombre"] == dia_l_pref]
                prob += lpSum([asig[g][d][t] for d in d_ley_g for t in LISTA_TURNOS]) <= (len(d_ley_g) - 2)

            prob.solve(PULP_CBC_CMD(msg=0, timeLimit=30))

            if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
                # Mapear resultados de grupos a empleados individuales
                res_final = []
                for di in dias_info:
                    for g in nombres_g:
                        t_grupo = "---"
                        for t in LISTA_TURNOS:
                            if value(asig[g][di["n"]][t]) == 1: t_grupo = t
                        
                        # Asignar este turno a todos los miembros del grupo
                        miembros = df_grupos[df_grupos['grupo'] == g]
                        for _, m in miembros.iterrows():
                            res_final.append({
                                "Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], 
                                "Semana": di["semana"], "Empleado": m['nombre'], "Grupo": g,
                                "Cargo": m['cargo'], "Turno": t_grupo, "Contrato": m['descanso_ley']
                            })
                
                df_res = pd.DataFrame(res_final)
                lista_procesada = []
                for emp, grupo_emp in df_res.groupby("Empleado"):
                    grupo_emp = grupo_emp.sort_values("Dia").copy()
                    dl = grupo_emp['Contrato'].iloc[0][:3]
                    
                    # Semanas a compensar
                    semanas_t = []
                    for s in semanas_mes:
                        dia_l = grupo_emp[(grupo_emp['Semana'] == s) & (grupo_emp['Nom_Dia'] == dl)]
                        if not dia_l.empty:
                            if dia_l['Turno'].iloc[0] in LISTA_TURNOS:
                                semanas_t.append(s)
                            else:
                                grupo_emp.loc[dia_l.index, 'Turno'] = 'DESC. LEY'
                    
                    # Pagar compensatorios
                    for st_deuda in semanas_t:
                        idx_c = grupo_emp[(grupo_emp['Semana'] == st_deuda + 1) & (grupo_emp['Turno'] == '---') & (~grupo_emp['Nom_Dia'].isin(['Vie','Sab','Dom']))].head(1).index
                        if not idx_c.empty: grupo_emp.loc[idx_c, 'Turno'] = 'DESC. COMPENSATORIO'
                    
                    grupo_emp.loc[grupo_emp['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
                    lista_procesada.append(grupo_emp)

                st.session_state['df_final'] = pd.concat(lista_procesada)
                status.update(label="✅ Malla por Células Generada", state="complete", expanded=False)

    if 'df_final' in st.session_state:
        df_v = st.session_state['df_final']
        
        t1, t2 = st.tabs(["📅 Malla Individual", "👥 Resumen de Células"])
        
        with t1:
            m_piv = df_v.pivot(index=['Grupo', 'Empleado'], columns='Label', values='Turno')
            st.dataframe(m_piv.style.applymap(lambda v: 'background-color: #fee2e2' if 'LEY' in str(v) else ('background-color: #fef9c3' if 'COMP' in str(v) else '')), use_container_width=True)

        with t2:
            st.markdown("### Configuración de Grupos")
            for g_id, data in df_grupos.groupby("grupo"):
                with st.container():
                    st.markdown(f"<div class='group-card'><b>{g_id}</b> - Descanso Ley: {data['descanso_ley'].iloc[0]}<br>"
                                f"Integrantes: {len(data)} (2 Master, 7 Tec A, 3 Tec B)</div>", unsafe_allow_html=True)
