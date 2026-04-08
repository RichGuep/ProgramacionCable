import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")
st.title("🗓️ Programación: Estabilidad y Protección del Sueño")

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

# --- 2. CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Parámetros")
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
dias_info = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_info.append({
        "n": d, 
        "nombre": dias_esp[fecha.weekday()], 
        "semana": n_semana,
        "label": f"{d} - {dias_esp[fecha.weekday()]}"
    })

# --- 4. MOTOR ---
if st.button(f"🚀 Generar Programación"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Estabilidad_Higiene", LpMaximize)
    
    # Variables
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')
    mantiene = LpVariable.dicts("Mantiene", (df_f[col_nom], range(2, num_dias + 1), turnos), cat='Binary')

    # OBJETIVO: Cobertura + Premio por no cambiar turno (Estabilidad)
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos]) + \
            lpSum([mantiene[e][d][t] * 0.5 for e in df_f[col_nom] for d in range(2, num_dias + 1) for t in turnos])

    for d_i in dias_info:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e = row[col_nom]
        dia_c_nom = "Sab" if "sabado" in row[col_des] else "Dom"
        
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            
            # HIGIENE DEL SUEÑO
            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                
                # REGLA DE ESTABILIDAD
                for t in turnos:
                    prob += mantiene[e][d+1][t] <= asig[e][d][t]
                    prob += mantiene[e][d+1][t] <= asig[e][d+1][t]

        # Descansos Finde y Reforma
        d_f_m = [di["n"] for di in dias_info if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in d_f_m for t in turnos]) == (len(d_f_m) - 2)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 21

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento final corregido
        res_list = []
        for d_i in dias_info:
            d = d_i["n"]
            for e in df_f[col_nom]:
                t_asig = "---"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res_list.append({
                    "Dia": d, "Label": d_i["label"], "Semana": d_i["semana"], 
                    "Nom_Dia": d_i["nombre"], "Empleado": e, "Turno": t_asig,
                    "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]
                })
        
        df_res = pd.DataFrame(res_list)
        
        # Asignación de Descansos/DISPO
        lista_final = []
        for emp, grupo in df_res.groupby("Empleado"):
            grupo = grupo.copy()
            d_c_n = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            # 2 Libres contractuales
            idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == d_c_n)].head(2).index
            grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
            # 2 Compensatorios L-V
            idx_c = grupo[(grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(2).index
            grupo.loc[idx_c, 'Turno'] = 'DESC. L-V'
            # Resto DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

        # Estilo de Celdas
        def style_fn(val):
            if val == 'DESC. CONTRATO': return 'background-color: #ffb3b3; color: #b30000; font-weight: bold'
            if val == 'DESC. L-V': return 'background-color: #ffd9b3; color: #804000; font-weight: bold'
            if val == 'DISPO': return 'background-color: #e6f3ff; color: #004080'
            return ''

        # --- VISTAS ---
        if tipo_vista == "Mes Completo":
            m_full = df_final.pivot(index='ID', columns='Label', values='Turno')
            # Reordenar columnas para que 10 no vaya antes que 2
            cols_sorted = sorted(m_full.columns, key=lambda x: int(x.split(' - ')[0]))
            st.dataframe(m_full[cols_sorted].style.map(style_fn), use_container_width=True)
        else:
            sems = sorted(df_final['Semana'].unique())
            tabs = st.tabs([f"Semana {s}" for s in sems])
            for i, s in enumerate(sems):
                with tabs[i]:
                    m_s = df_final[df_final['Semana'] == s].pivot(index='ID', columns='Label', values='Turno')
                    cols_s = sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))
                    st.dataframe(m_s[cols_s].style.map(style_fn), use_container_width=True)

        st.success("✅ Programación generada con enfoque en estabilidad y higiene del sueño.")
    else:
        st.error("❌ No hay solución. Revisa el balance personal/cupos.")
