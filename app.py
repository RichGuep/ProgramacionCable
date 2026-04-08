import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programación Inteligente: Higiene del Sueño y Auditoría")

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
    st.header("📅 Periodo y Cargo")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    
    cargo_sel = st.selectbox("Filtrar por Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo objetivo por turno", value=2)
    
    st.divider()
    st.info("Regla: No se permite pasar de NOCHE a AM/PM, ni de PM a AM al día siguiente.")

# --- 3. LÓGICA DE CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = [{"n": d, "nombre": ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"][datetime(ano_sel, mes_num, d).weekday()]} for d in range(1, num_dias + 1)]

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla y Auditoría {mes_sel}"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Higiene_Sueno", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    # OBJETIVO: Maximizar cobertura operativa
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    # Restricciones de Cupo
    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    # Restricciones por Empleado
    for _, row in df_f.iterrows():
        e, contrato = row[col_nom], row[col_des]
        dia_c = "Sabado" if "sabado" in contrato else "Domingo"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # HIGIENE DEL SUEÑO
            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # Días laborales totales (Reforma Laboral)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) == int((num_dias / 7) * 5)
        
        # Descansos Finde (Exactamente 2 libres)
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento para asignar DESCANSO y DISPO
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia": d["n"], "Nombre": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c = "Sabado" if "sabado" in grupo['Contrato'].iloc[0] else "Domingo"
            
            idx_libres_f = grupo[(grupo['Turno'] == '---') & (grupo['Nombre'] == dia_c)].head(2).index
            grupo.loc[idx_libres_f, 'Turno'] = 'DESCANSO'
            
            max_libres = num_dias - int((num_dias / 7) * 5)
            idx_restantes = grupo[grupo['Turno'] == '---'].index
            for idx in idx_restantes:
                if len(grupo[grupo['Turno'] == 'DESCANSO']) < max_libres:
                    grupo.loc[idx, 'Turno'] = 'DESCANSO'
                else:
                    grupo.loc[idx, 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_f_final = pd.concat(lista_final).reset_index(drop=True)

        # --- VISUALIZACIÓN ---
        st.success(f"✅ Malla generada para {cargo_sel}")
        
        tab1, tab2, tab3 = st.tabs(["📅 Malla Mensual", "👤 Auditoría Individual", "🛡️ Cobertura"])

        with tab1:
            df_f_final['ID'] = df_f_final['Empleado'] + " (" + df_f_final['Contrato'].str.upper() + ")"
            malla_p = df_f_final.pivot(index='ID', columns='Dia', values='Turno')
            st.dataframe(malla_p.reindex(columns=range(1, num_dias + 1)), use_container_width=True)

        with tab2:
            st.subheader("📋 Resumen por Persona")
            auditoria = []
            for e, g in df_f_final.groupby("Empleado"):
                c = g['Contrato'].iloc[0]
                d_c = "Sabado" if "sabado" in c else "Domingo"
                auditoria.append({
                    "Empleado": e, "Contrato": c.upper(),
                    "Libres Finde": f"{len(g[(g['Nombre']==d_c) & (g['Turno']=='DESCANSO')])}/2",
                    "Compensatorios L-V": len(g[(~g['Nombre'].isin(['Sabado','Domingo'])) & (g['Turno']=='DESCANSO')]),
                    "Días DISPO": len(g[g['Turno'] == 'DISPO'])
                })
            st.table(pd.DataFrame(auditoria))

        with tab3:
            st.subheader("🚩 Faltantes por Turno")
            faltantes = []
            for d_i in dias_mes:
                for t in turnos:
                    c = len(df_f_final[(df_f_final['Dia']==d_i['n']) & (df_f_final['Turno']==t)])
                    if c < cupo_manual:
                        faltantes.append({"Dia": d_i['n'], "Turno": t, "Faltan": cupo_manual - c})
            if faltantes: st.warning("Turnos incompletos"); st.table(pd.DataFrame(faltantes))
            else: st.success("¡Cobertura completa!")
    else:
        st.error("❌ No hay solución lógica. Revisa los cupos o el personal.")
