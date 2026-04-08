import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro - Estabilidad Total", layout="wide")
st.title("🗓️ Programación con Higiene del Sueño y Estabilidad de Turno")

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
    st.divider()
    tipo_vista = st.radio("Visualización:", ["Vista por Semanas", "Mes Completo"])

# --- 3. LÓGICA DE CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_mes = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_mes.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana})

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla con Protección de Sueño"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Estable", LpMaximize)
    
    # Variables principales
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')
    # Variable auxiliar para estabilidad (indica si el empleado mantiene el turno de ayer)
    estables = LpVariable.dicts("Estable", (df_f[col_nom], range(2, num_dias + 1)), cat='Binary')

    # FUNCIÓN OBJETIVO: Maximizar cobertura + Incentivar estabilidad (0.1 puntos por mantener turno)
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos]) + \
            lpSum([estables[e][d] * 0.1 for e in df_f[col_nom] for d in range(2, num_dias + 1)])

    # Restricciones de Cupo
    for d_i in dias_mes:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e, contrato = row[col_nom], row[col_des]
        dia_c_nom = "Sab" if "sabado" in contrato else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # --- PROTECCIÓN DEL SUEÑO (SEGURIDAD) ---
            if d < num_dias:
                # Si es Noche (termina mañana), hoy NO puede entrar en AM ni PM
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                # Si es PM (termina tarde), hoy NO puede entrar en AM (madrugada)
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                
                # --- LÓGICA DE ESTABILIDAD ---
                # estables[e][d] solo puede ser 1 si el turno de hoy es igual al de ayer
                for t in turnos:
                    prob += estables[e][d] <= 1 - (asig[e][d-1][t] - asig[e][d][t])
                    prob += estables[e][d] <= 1 - (asig[e][d][t] - asig[e][d-1][t])

        # Descansos Legales
        d_f_m = [di["n"] for di in dias_mes if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 22

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Post-procesamiento
        lista_final = []
        for emp, grupo in pd.DataFrame([{"Dia": d["n"], "Label": f"{d['n']} - {d['nombre']}", "Semana": d["semana"], "Nom_Dia": d["nombre"], "Empleado": e, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0], "Turno": next((t for t in turnos if value(asig[e][d["n"]][t]) == 1), "---")} for d in dias_mes for e in df_f[col_nom]]).groupby("Empleado"):
            grupo = grupo.copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            
            idx_c = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[idx_c, 'Turno'] = 'DESC. CONTRATO'
            idx_comp = grupo[(grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(3).index
            grupo.loc[idx_comp, 'Turno'] = 'DESC. L-V'
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

        # Estilo de celdas
        def style_fn(val):
            if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        # --- MOSTRAR VISTAS ---
        if tipo_vista == "Mes Completo":
            st.subheader(f"📅 Malla Mensual: {mes_sel}")
            malla_full = df_final.pivot(index='ID', columns='Label', values='Turno')
            st.dataframe(malla_full.style.map(style_fn), use_container_width=True)
        else:
            semanas = sorted(df_final['Semana'].unique())
            tabs = st.tabs([f"Semana {s}" for s in semanas])
            for i, s in enumerate(semanas):
                with tabs[i]:
                    m_sem = df_final[df_final['Semana'] == s].pivot(index='ID', columns='Label', values='Turno')
                    st.dataframe(m_sem.style.map(style_fn), use_container_width=True)

        # Auditoría
        st.divider()
        st.subheader("📊 Auditoría de Descansos y Estabilidad")
        res = []
        for e, g in df_final.groupby("Empleado"):
            turnos_unicos = g[g['Turno'].isin(turnos)]['Turno'].unique()
            res.append({
                "Empleado": e, "Contrato": g['Contrato'].iloc[0].upper(),
                "Desc. Finde": len(g[g['Turno']=='DESC. CONTRATO']),
                "Compensatorios L-V": len(g[g['Turno']=='DESC. L-V']),
                "DISPO": len(g[g['Turno']=='DISPO']),
                "Turnos usados": " / ".join(turnos_unicos)
            })
        st.table(pd.DataFrame(res))
    else:
        st.error("❌ Conflicto de reglas. El personal es insuficiente para dar descansos y mantener turnos estables.")
