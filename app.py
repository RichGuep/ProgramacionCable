import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro - Optimización de Descansos", layout="wide")

st.title("🗓️ Programación con Límite de Compensatorios")

# --- 1. CARGA DE DATOS ---
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
    st.error(f"Error al leer el archivo: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("📅 Configuración")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)

# --- 3. LÓGICA DE DÍAS ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()]} for d in range(1, num_dias + 1)]
lista_cols = [f"{d['n']} - {d['nombre']}" for d in dias_mes]

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla Optimizada"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Minimizar_Descansos", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    # OBJETIVO: Maximizar días trabajados (para que no descansen por descansar)
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
            if d < num_dias: # Sueño
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # --- AJUSTE DE DESCANSOS ---
        # 1. Exactamente 2 descansos de fin de semana contractual
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)

        # 2. LIMITAR TRABAJO: Trabajará entre 22 y 24 días (Para bajar de 9 a 4-6 descansos)
        # Esto obliga a que la persona esté DISPO en lugar de DESCANSO
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 22

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia_Num": d["n"], "Dia_Label": f"{d['n']} - {d['nombre']}", "Nombre_Dia": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            
            # Marcar 2 descansos contractuales
            libres_f = grupo[(grupo['Turno'] == '---') & (grupo['Nombre_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[libres_f, 'Turno'] = 'DESCANSO'
            
            # Marcar MÁXIMO 3 compensatorios L-V (como pediste)
            libres_lv = grupo[(grupo['Turno'] == '---') & (~grupo['Nombre_Dia'].isin(['Sab', 'Dom']))].head(3).index
            grupo.loc[libres_lv, 'Turno'] = 'DESCANSO'
            
            # Todo lo demás que sobre es DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"
        
        # Estilización
        malla_p = df_final.pivot(index='ID', columns='Dia_Label', values='Turno').reindex(columns=lista_cols)
        
        def style_turnos(val):
            if val == 'DESCANSO': return 'background-color: #ffcccc; color: #cc0000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        st.subheader("📅 Malla Optimizada (Abril 2026)")
        st.dataframe(malla_p.style.map(style_turnos), use_container_width=True)
        
        # Auditoría Actualizada
        st.subheader("📊 Auditoría de Descansos Reales")
        auditoria = []
        for e, g in df_final.groupby("Empleado"):
            auditoria.append({
                "Empleado": e,
                "Días Trabajados": len(g[g['Turno'].isin(['AM','PM','Noche'])]),
                "Descansos Totales": len(g[g['Turno'] == 'DESCANSO']),
                "Disponibilidades": len(g[g['Turno'] == 'DISPO'])
            })
        st.table(pd.DataFrame(auditoria))
    else:
        st.error("❌ No hay solución con 22 días mínimos de trabajo. Prueba bajando a 21.")
