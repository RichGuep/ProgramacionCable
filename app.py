import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026 - Estabilidad", layout="wide")
st.title("🗓️ Programador de Turnos: Enfoque en Estabilidad de Jornada")

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
    st.error(f"Error al leer archivo: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("⚙️ Configuración")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)
    st.divider()
    tipo_vista = st.radio("Ver Malla por:", ["Semanas", "Mes Completo"])

# --- 3. CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_mes.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana})

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla Estable"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Estable", LpMaximize)
    
    # Variables de asignación
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')
    
    # Variable de estabilidad: 1 si el empleado mantiene el turno del día anterior
    mantiene = LpVariable.dicts("Mantiene", (df_f[col_nom], range(2, num_dias + 1), turnos), cat='Binary')

    # FUNCIÓN OBJETIVO: Cobertura + Premio por estabilidad
    # El premio (0.5) es lo suficientemente alto para que el modelo prefiera no rotar si no es obligatorio.
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos]) + \
            lpSum([mantiene[e][d][t] * 0.5 for e in df_f[col_nom] for d in range(2, num_dias + 1) for t in turnos])

    # Restricciones
    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e = row[col_nom]
        dia_c_nom = "Sab" if "sabado" in row[col_des] else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # HIGIENE DEL SUEÑO (Protección estricta)
            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                
                # LÓGICA DE ESTABILIDAD: mantiene[d] solo es 1 si asig[d] y asig[d-1] son iguales
                for t in turnos:
                    prob += mantiene[e][d+1][t] <= asig[e][d][t]
                    prob += mantiene[e][d+1][t] <= asig[e][d+1][t]

        # Descansos Legales y Reforma
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 21

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento final
        res = []
        for d_i in dias_mes:
            d = d_i["n"]
            for e in df_f[col_nom]:
                t_asig = "---"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res.append({
                    "Dia": d, "Label": f"{d['n']} - {d['nombre']}", "Semana": d["semana"], 
                    "Nom_Dia": d_i["nombre"], "Empleado": e, "Turno": t_asig,
                    "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]
                })
        
        df_res = pd.DataFrame(res)
        
        # Asignar Descansos y DISPO de forma lógica
        lista_final = []
        for emp, grupo in df_res.groupby("Empleado"):
            grupo = grupo.copy()
            d_c_n = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            # 2 Libres finde
            idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == d_c_n)].head(2).index
            grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
            # 2 Libres compensatorios
            idx_c = grupo[(grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(2).index
            grupo.loc[idx_c, 'Turno'] = 'DESC. L-V'
            # Resto DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

        # Estilo
        def color_map(val):
            if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        # Mostrar Resultados
        if tipo_vista == "Mes Completo":
            m_f = df_final.pivot(index='ID', columns='Label', values='Turno')
            st.dataframe(m_f.style.map(color_map), use_container_width=True)
        else:
            sems = sorted(df_final['Semana'].unique())
            tabs = st.tabs([f"Semana {s}" for s in sems])
            for i, s in enumerate(sems):
                with tabs[i]:
                    m_s = df_final[df_final['Semana'] == s].pivot(index='ID', columns='Label', values='Turno')
                    st.dataframe(m_s.style.map(color_map), use_container_width=True)

        # Auditoría de Estabilidad
        st.divider()
        st.subheader("📊 Auditoría de Estabilidad Laboral")
        audit = []
        for e, g in df_final.groupby("Empleado"):
            turnos_usados = g[g['Turno'].isin(turnos)]['Turno'].unique()
            audit.append({
                "Empleado": e, 
                "Turnos Diferentes en el Mes": len(turnos_usados),
                "Horarios Asignados": " / ".join(turnos_usados),
                "Estatus": "✅ ESTABLE" if len(turnos_usados) <= 2 else "⚠️ ROTACIÓN ALTA"
            })
        st.table(pd.DataFrame(audit))
    else:
        st.error("❌ No hay solución. Revisa el balance personal/cupos.")
