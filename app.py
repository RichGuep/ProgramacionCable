import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["AM", "PM", "Noche"]

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #f8fafc; }
    div.stButton > button { background-color: #2563eb; color: white; font-weight: bold; border-radius: 10px; height: 52px; border: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIN ---
def login_page():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        _, col_login, _ = st.columns([1, 1.8, 1])
        with col_login:
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown("<h1 style='text-align:center; color:#1a365d;'>MovilGo</h1>", unsafe_allow_html=True)
            with st.form("LoginForm"):
                user = st.text_input("Correo Corporativo")
                pwd = st.text_input("Contraseña", type="password")
                if st.form_submit_button("INGRESAR"):
                    if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                        st.session_state['auth'] = True; st.session_state['user_name'] = "Richard Guevara"; st.rerun()
        st.stop()

login_page()

# --- 4. MOTOR ---
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
        cupo_manual = st.number_input("Cupo Mínimo por Turno", 1, 15, 2)

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    if st.button("🚀 GENERAR MALLA PRIORIZANDO COBERTURA"):
        progress_bar = st.progress(0); status_text = st.empty()
        
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        prob = LpProblem("MovilGo_Cobertura_Total", LpMaximize)
        asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (range(1, num_dias + 1), LISTA_TURNOS), lowBound=0, cat='Integer')

        # OBJETIVO: Cobertura total (hueco penalizado con 10,000 puntos)
        prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) - \
                lpSum([hueco[d][t] * 10000 for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

        for di in dias_info:
            for t in LISTA_TURNOS:
                prob += lpSum([asig[e][di["n"]][t] for e in df_f['nombre']]) + hueco[di["n"]][t] >= cupo_manual

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_l_nom = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            for d in range(1, num_dias + 1):
                prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum([asig[e][d+1][t] for t in LISTA_TURNOS]) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
            
            dias_criticos = [di["n"] for di in dias_info if di["nombre"] == dia_l_nom]
            prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) == (len(dias_criticos) - 2)

        status_text.text("Calculando cobertura óptima...")
        progress_bar.progress(50)
        prob.solve(PULP_CBC_CMD(msg=0, timeLimit=25))

        if LpStatus[prob.status] in ['Optimal', 'Not Solved']:
            res_list = []
            for di in dias_info:
                for e in df_f['nombre']:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[e][di["n"]][t]) == 1: t_asig = t
                    res_list.append({"Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nombre"], "Empleado": e, "Turno": t_asig, "Ley_Descanso": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})
            
            df_res = pd.DataFrame(res_list)
            lista_final = []
            for emp, grupo in df_res.groupby("Empleado"):
                grupo = grupo.sort_values("Dia").reset_index(drop=True)
                t_mode = grupo[grupo['Turno'].isin(LISTA_TURNOS)]['Turno'].mode()
                t_base = t_mode[0] if not t_mode.empty else "AM"
                
                # --- SOLUCIÓN AL KEYERROR: Usar rango de posiciones reales ---
                for i in range(len(grupo)):
                    if grupo.loc[i, 'Turno'] == '---':
                        dia_act = grupo.loc[i, 'Nom_Dia']
                        dia_ley = "Sab" if "sab" in str(grupo.loc[i, 'Ley_Descanso']).lower() else "Dom"
                        
                        # Si es día de contrato y está vacío, es descanso de ley
                        if dia_act == dia_ley:
                            if len(grupo[grupo['Turno'] == 'DESC. LEY']) < 2:
                                grupo.loc[i, 'Turno'] = 'DESC. LEY'
                            else:
                                grupo.loc[i, 'Turno'] = f"DISPONIBLE {t_base}"
                        # Si el día anterior fue noche (usando posición i-1 segura)
                        elif i > 0 and grupo.loc[i-1, 'Turno'] == 'Noche':
                            grupo.loc[i, 'Turno'] = 'DESC. COMPENSATORIO'
                        else:
                            grupo.loc[i, 'Turno'] = f"DISPONIBLE {t_base}"
                lista_final.append(grupo)
            
            st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
            status_text.empty(); progress_bar.empty()
        else:
            st.error("No se pudo generar la malla. Revisa los cupos.")

    if 'df_final' in st.session_state:
        m_f = st.session_state['df_final'].pivot(index='Empleado', columns='Label', values='Turno')
        st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))], use_container_width=True)
