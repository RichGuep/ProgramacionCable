import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")

st.title("🗓️ Programación con Estilo y Nombres de Día")

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

# --- 3. LÓGICA DE CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()]} for d in range(1, num_dias + 1)]
lista_columnas_bonitas = [f"{d['n']} - {d['nombre']}" for d in dias_mes]

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla Estilizada {mes_sel}"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Estilo", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

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

        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) == int((num_dias / 7) * 5)
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia_Num": d["n"], "Dia_Label": f"{d['n']} - {d['nombre']}", "Nombre_Dia": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            idx_libres_f = grupo[(grupo['Turno'] == '---') & (grupo['Nombre_Dia'] == dia_c_nom)].head(2).index
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

        # --- VISUALIZACIÓN CON COLOR ---
        st.success(f"✅ Malla generada para {cargo_sel}")
        
        df_f_final['ID'] = df_f_final['Empleado'] + " (" + df_f_final['Contrato'].str.upper() + ")"
        malla_p = df_f_final.pivot(index='ID', columns='Dia_Label', values='Turno')
        
        # Reordenar columnas para que sigan el orden 1, 2, 3...
        malla_p = malla_p.reindex(columns=lista_columnas_bonitas)

        # Función para dar color
        def color_descanso(val):
            if val == 'DESCANSO':
                return 'background-color: #ffcccc; color: #cc0000; font-weight: bold' # Rojo suave
            if val == 'DISPO':
                return 'background-color: #e6f3ff; color: #004080' # Azul suave
            return ''

        st.subheader("📅 Malla Mensual Detallada")
        st.dataframe(malla_p.style.applymap(color_descanso), use_container_width=True)
        
        # --- MÉTRICAS ---
        with st.expander("📊 Ver Auditoría de Cumplimiento"):
            auditoria = []
            for e, g in df_f_final.groupby("Empleado"):
                auditoria.append({
                    "Empleado": e, "Descansos Finde": f"{len(g[g['Turno']=='DESCANSO' & g['Nombre_Dia'].isin(['Sab','Dom'])])}/2",
                    "Días Laborados": len(g[g['Turno'].isin(['AM','PM','Noche'])])
                })
            st.table(pd.DataFrame(auditoria))
    else:
        st.error("❌ No hay solución lógica.")
