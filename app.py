import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro - Auditoría Detallada", layout="wide")
st.title("🗓️ Programación con Discriminación de Descansos y Compensatorios")

# --- 1. CARGA ---
try:
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    col_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), None)
    col_car = next((c for c in df.columns if 'car' in c), None)
    col_des = next((c for c in df.columns if 'des' in c), None)
    df[col_nom] = df[col_nom].astype(str).str.strip()
    df[col_car] = df[col_car].astype(str).str.strip()
    df[col_des] = df[col_des].astype(str).str.strip().str.lower()
except Exception as e:
    st.error(f"Error: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("⚙️ Configuración")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)

# --- 3. CÁLCULOS DE CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()]} for d in range(1, num_dias + 1)]
lista_cols = [f"{d['n']} - {d['nombre']}" for d in dias_mes]

# --- 4. MOTOR ---
if st.button(f"🚀 Generar Malla con Auditoría Discriminada"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Discriminada", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    # Maximizar trabajo para evitar descansos innecesarios
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e, contrato = row[col_nom], row[col_des]
        dia_c_nom = "Sab" if "sabado" in contrato else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            if d < num_dias: # Higiene del sueño
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # Restricción: 2 descansos contractuales exactamente
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)
        
        # Mínimo de días laborados para evitar el exceso de descansos (Reforma)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 22

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento Detallado
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia_Num": d["n"], "Dia_Label": f"{d['n']} - {d['nombre']}", "Nombre_Dia": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            
            # 1. Identificar Descansos de Fin de Semana (Contractuales)
            idx_contrato = grupo[(grupo['Turno'] == '---') & (grupo['Nombre_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[idx_contrato, 'Turno'] = 'DESC. CONTRATO'
            
            # 2. Identificar Compensatorios Lunes a Viernes (Máximo 3)
            idx_comp = grupo[(grupo['Turno'] == '---') & (~grupo['Nombre_Dia'].isin(['Sab', 'Dom']))].head(3).index
            grupo.loc[idx_comp, 'Turno'] = 'DESC. L-V'
            
            # 3. Marcar el resto como DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            # Otros descansos que no entraron en las categorías anteriores por ser fines de semana no contractuales
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO' 
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)

        # --- VISUALIZACIÓN ---
        st.subheader(f"Malla de Turnos: {mes_sel} {ano_sel}")
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"
        malla_p = df_final.pivot(index='ID', columns='Dia_Label', values='Turno').reindex(columns=lista_cols)
        
        def estilo_celdas(val):
            if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        st.dataframe(malla_p.style.map(estilo_celdas), use_container_width=True)

        # --- MÉTRICAS DISCRIMINADAS ---
        st.divider()
        st.subheader("📊 Discriminación de Descansos por Persona")
        resumen = []
        for e, g in df_final.groupby("Empleado"):
            resumen.append({
                "Empleado": e,
                "Tipo Contrato": g['Contrato'].iloc[0].upper(),
                "Descansos Finde (Contrato)": len(g[g['Turno'] == 'DESC. CONTRATO']),
                "Compensatorios (Lunes-Viernes)": len(g[g['Turno'] == 'DESC. L-V']),
                "Días en DISPONIBILIDAD": len(g[g['Turno'] == 'DISPO']),
                "Total Días Trabajados": len(g[g['Turno'].isin(['AM','PM','Noche'])])
            })
        st.table(pd.DataFrame(resumen))
    else:
        st.error("No se pudo balancear. Prueba bajando ligeramente el cupo o el mínimo de días laborados.")
