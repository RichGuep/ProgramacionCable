import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026", layout="wide")
st.title("🗓️ Programador de Turnos Inteligente: Calendario Dinámico")

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
    st.error(f"Error al leer Excel: {e}"); st.stop()

# --- 2. PARAMETRIZACIÓN DE TIEMPO (NUEVO) ---
with st.sidebar:
    st.header("📅 Periodo a Programar")
    hoy = datetime.now()
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel_nombre = st.selectbox("Mes", meses_nombres, index=hoy.month - 1)
    mes_num = meses_nombres.index(mes_sel_nombre) + 1

    st.divider()
    st.header("⚙️ Cupos Operativos")
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input(f"Cupo por turno", value=2 if "master" in cargo_sel.lower() else 7)

# --- 3. LÓGICA DE CALENDARIO ---
# Obtenemos los días exactos del mes seleccionado
num_dias_mes = calendar.monthrange(ano_sel, mes_num)[1]
lista_dias = []
dias_semana_esp = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

for dia in range(1, num_dias_mes + 1):
    fecha = datetime(ano_sel, mes_num, dia)
    nombre_dia = dias_semana_esp[fecha.weekday()]
    lista_dias.append({"fecha": dia, "nombre": nombre_dia})

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Programación {mes_sel_nombre} {ano_sel}"):
    df_f = df[df[col_car] == cargo_sel]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Malla_Dinamica", LpMinimize)
    # Variable: asig[empleado, dia_del_mes, turno]
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias_mes + 1), turnos), cat='Binary')

    # A. RESTRICCIÓN DE CUPO DIARIO
    for d_info in lista_dias:
        d = d_info["fecha"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) == cupo_manual

    # B. RESTRICCIONES POR EMPLEADO
    for _, row in df_f.iterrows():
        e = row[col_nom]
        contrato = row[col_des]
        dia_contrato_nombre = "Sabado" if "sabado" in contrato else "Domingo"
        
        # 1. Un turno al día máximo
        for d in range(1, num_dias_mes + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
        
        # 2. Descanso Biológico (No Noche -> AM/PM al día siguiente)
        for d in range(1, num_dias_mes):
            prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
            prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

        # 3. GARANTÍA DE DESCANSO FIN DE SEMANA (Mínimo 2 Libres en el mes)
        # Filtramos los días del mes que coinciden con su día de contrato
        dias_contrato_mes = [di["fecha"] for di in lista_dias if di["nombre"] == dia_contrato_nombre]
        prob += lpSum([asig[e][d][t] for d in dias_contrato_mes for t in turnos]) <= (len(dias_contrato_mes) - 2)

        # 4. REFORMA LABORAL: Promedio 2 días de descanso por cada 7 días
        # Calculamos cuántos días debe trabajar en total el mes para cumplir con la ley
        dias_laborables_objetivo = int((num_dias_mes / 7) * 5)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias_mes + 1) for t in turnos]) == dias_laborables_objetivo

    # RESOLVER
    with st.spinner("Calculando malla óptima..."):
        prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success(f"✅ Programación de {mes_sel_nombre} generada exitosamente.")
        
        res_list = []
        for d_info in lista_dias:
            d = d_info["fecha"]
            for e in df_f[col_nom]:
                t_asig = "DESCANSO"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res_list.append({"Dia": d, "Nombre_Dia": d_info["nombre"], "Empleado": e, "Turno": t_asig})
        
        df_res = pd.DataFrame(res_list)
        
        # Visualización: Dividimos por semanas para que no sea una tabla gigante
        num_semanas = (num_dias_mes // 7) + 1
        for s in range(num_semanas):
            inicio = s * 7 + 1
            fin = min((s + 1) * 7, num_dias_mes)
            if inicio <= num_dias_mes:
                st.subheader(f"Del {inicio} al {fin} de {mes_sel_nombre}")
                malla_sem = df_res[(df_res['Dia'] >= inicio) & (df_res['Dia'] <= fin)]
                malla_pivot = malla_sem.pivot(index='Empleado', columns='Dia', values='Turno')
                st.dataframe(malla_pivot, use_container_width=True)

    else:
        st.error("❌ No hay solución. Revisa que el personal sea suficiente para los cupos.")
