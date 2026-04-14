import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. PARÁMETROS LEGALES 2026 ---
st.set_page_config(page_title="MovilGo Pro v3", layout="wide", page_icon="⚡")
JORNADA_LEGAL = 7.33  
VALOR_HORA_MES = 182 # Nueva base 42h/semanales
LISTA_TURNOS = ["AM", "PM", "Noche"]

INFO_TURNOS = {
    "AM": {"nocturnas": 0},
    "PM": {"nocturnas": 2.5}, # Recargo desde las 19:00
    "Noche": {"nocturnas": 8}
}

MESES_MAP = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
}

# --- 2. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_des = next((c for c in df.columns if 'des' in c), "descanso")
        c_sal = next((c for c in df.columns if 'sal' in c), "salario")
        return df.rename(columns={c_des: 'descanso_ley', c_sal: 'salario_base'})
    except: return None

df_raw = load_data()

# --- 3. INTERFAZ SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración 2026")
    ano_sel = st.selectbox("Año", [2026], index=0)
    mes_sel = st.selectbox("Mes", list(MESES_MAP.keys()), index=datetime.now().month - 1)
    mes_num = MESES_MAP[mes_sel]
    cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()) if df_raw is not None else ["Sin Datos"])
    cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)

# --- 4. MOTOR DE OPTIMIZACIÓN Y ROTACIÓN ---
if st.button("🚀 GENERAR MALLA ÓPTIMA CON REFORMA"):
    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    dias_info = [{"n": d, "nom": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

    prob = LpProblem("MovilGo_Rotation", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')

    # Maximizar cobertura
    prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

    # Restricciones de rotación y salud
    for e in df_f['nombre']:
        row_e = df_f[df_f['nombre'] == e].iloc[0]
        dia_ley_nom = "Sab" if "sab" in str(row_e['descanso_ley']).lower() else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1 # Solo 1 turno/día
            if d < num_dias: # Higiene del sueño
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # Garantizar al menos 2 descansos de ley al mes (Rotación de findes)
        dias_criticos = [di["n"] for di in dias_info if di["nom"] == dia_ley_nom]
        prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)

    # Cupos por turno
    for d in range(1, num_dias + 1):
        for t in LISTA_TURNOS:
            prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) <= cupo_manual

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # --- PROCESAMIENTO DE RESULTADOS ---
        final_rows = []
        for e in df_f['nombre']:
            row_e = df_f[df_f['nombre'] == e].iloc[0]
            dia_ley_nom = "Sab" if "sab" in str(row_e['descanso_ley']).lower() else "Dom"
            v_hora = row_e['salario_base'] / VALOR_HORA_MES

            for di in dias_info:
                t_asig = "---"
                for t in LISTA_TURNOS:
                    if value(asig[e][di["n"]][t]) == 1: t_asig = t
                
                final_rows.append({
                    "Empleado": e, "Dia": di["n"], "Label": di["label"], "Nom_Dia": di["nom"],
                    "Turno": t_asig, "Salario": row_e['salario_base'], "V_Hora": v_hora, "Dia_Ley": dia_ley_nom
                })
        
        df_res = pd.DataFrame(final_rows)
        
        # --- LÓGICA DE DESCANSOS (Re-aplicada) ---
        lista_final = []
        for emp, grupo in df_res.groupby("Empleado"):
            grupo = grupo.sort_values("Dia").copy()
            dia_l = grupo['Dia_Ley'].iloc[0]
            
            # 1. Marcar Descansos de Ley
            idx_descanso = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_l)].index
            grupo.loc[idx_descanso, 'Turno'] = 'DESC. LEY'
            
            # 2. Compensatorios y Monetización
            for idx, row in grupo.iterrows():
                h_extra = 0; h_noc = 0; costo_rec = 0
                
                if row['Turno'] in LISTA_TURNOS:
                    h_extra = 8 - JORNADA_LEGAL
                    h_noc = INFO_TURNOS[row['Turno']]['nocturnas']
                    
                    # Calcular pesos (2026)
                    costo_rec += h_extra * (row['V_Hora'] * 1.25)
                    costo_rec += h_noc * (row['V_Hora'] * 0.35)
                    if row['Nom_Dia'] == dia_l: # Trabajó su día de ley
                        costo_rec += 8 * (row['V_Hora'] * 0.75)
                        # Buscar compensatorio en los siguientes 6 días
                        comp_idx = grupo[(grupo['Dia'] > row['Dia']) & (grupo['Dia'] <= row['Dia']+6) & (grupo['Turno'] == '---')].head(1).index
                        if not comp_idx.empty: grupo.loc[comp_idx, 'Turno'] = 'DESC. COMPENSATORIO'
                
                grupo.at[idx, 'Costo_R'] = costo_rec
                grupo.at[idx, 'H_Extra'] = h_extra if row['Turno'] in LISTA_TURNOS else 0
                grupo.at[idx, 'H_Noc'] = h_noc if row['Turno'] in LISTA_TURNOS else 0

            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPONIBILIDAD'
            lista_final.append(grupo)

        st.session_state['df_final'] = pd.concat(lista_final)
        st.success("✅ Malla Generada con Rotación y Ley 2026")

# --- 5. VISUALIZACIÓN ---
if 'df_final' in st.session_state:
    df_v = st.session_state['df_final']
    t1, t2, t3 = st.tabs(["📅 Malla Operativa", "💰 Auditoría 2026", "🔄 Rotación"])

    with t1:
        m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
        def color_turnos(v):
            if 'DESC. LEY' in v: return 'background-color: #ffb3b3'
            if 'COMPENSATORIO' in v: return 'background-color: #ffd9b3'
            return ''
        st.dataframe(m_piv.style.applymap(color_turnos), use_container_width=True)

    with t2:
        st.subheader("Desglose Financiero (Reforma Laboral)")
        resumen = df_v.groupby("Empleado").agg({
            "H_Extra": "sum", "H_Noc": "sum", "Costo_R": "sum", "Salario": "first"
        })
        resumen['Total_Nomina'] = resumen['Salario'] + resumen['Costo_R']
        st.table(resumen.style.format("${:,.0f}", subset=["Costo_R", "Salario", "Total_Nomina"]))
