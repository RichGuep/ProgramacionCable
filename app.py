import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")
st.title("🗓️ Programación: Estabilidad Semanal e Higiene del Sueño")

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
    tipo_vista = st.radio("Visualización:", ["Vista por Semanas", "Mes Completo"])

# --- 3. CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_mes.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana})

# --- 4. MOTOR ---
if st.button(f"🚀 Generar Programación"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Estable_Final", LpMaximize)
    
    # Variables de asignación
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')

    # OBJETIVO: Maximizar cobertura (Prioridad 1)
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    # A. Restricciones de Cupo
    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    # B. Restricciones por Empleado
    for _, row in df_f.iterrows():
        e = row[col_nom]
        contrato = row[col_des]
        dia_c_nom = "Sab" if "sabado" in contrato else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # --- PROTECCIÓN DEL SUEÑO (Reglas estrictas) ---
            if d < num_dias:
                # No pasar de Noche a AM o PM el día siguiente
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                # No pasar de PM a AM el día siguiente
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

        # Días laborales (Aprox 20-22 según el mes)
        dias_meta = int((num_dias / 7) * 5)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) == dias_meta
        
        # Descansos Finde (Exactamente 2 libres)
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia": d["n"], "Label": f"{d['n']} - {d['nombre']}", "Semana": d["semana"], "Nom_Dia": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            
            # Lógica de Descansos Contractuales
            idx_c = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[idx_c, 'Turno'] = 'DESC. CONTRATO'
            
            # Compensatorios L-V (Máximo 3)
            idx_comp = grupo[(grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(3).index
            grupo.loc[idx_comp, 'Turno'] = 'DESC. L-V'
            
            # El resto es DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

        # Colores
        def style_fn(val):
            if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        # --- VISTAS ---
        if tipo_vista == "Mes Completo":
            st.subheader(f"📅 Malla Mensual: {mes_sel}")
            malla_f = df_final.pivot(index='ID', columns='Label', values='Turno')
            st.dataframe(malla_f.style.map(style_fn), use_container_width=True)
        else:
            sems = sorted(df_final['Semana'].unique())
            tabs = st.tabs([f"Semana {s}" for s in sems])
            for i, s in enumerate(sems):
                with tabs[i]:
                    m_s = df_final[df_final['Semana'] == s].pivot(index='ID', columns='Label', values='Turno')
                    st.dataframe(m_s.style.map(style_fn), use_container_width=True)

        # Auditoría
        st.divider()
        st.subheader("📊 Resumen por Persona")
        res = []
        for e, g in df_final.groupby("Empleado"):
            res.append({
                "Empleado": e, "Contrato": g['Contrato'].iloc[0].upper(),
                "Desc. Finde": len(g[g['Turno']=='DESC. CONTRATO']),
                "Compensatorios L-V": len(g[g['Turno']=='DESC. L-V']),
                "DISPO": len(g[g['Turno']=='DISPO']),
                "Días Laborados": len(g[g['Turno'].isin(turnos)])
            })
        st.table(pd.DataFrame(res))
    else:
        st.error("❌ No hay solución. Revisa que el personal sea suficiente para cubrir los turnos sin romper las reglas de sueño.")
