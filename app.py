import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN Y PARÁMETROS LEGALES 2026 ---
st.set_page_config(page_title="MovilGo Pro - Reforma 2026", layout="wide", page_icon="⚡")

# Parámetros Reforma Laboral Colombia 2026
JORNADA_DIARIA_LEGAL = 7.33  # 7 horas y 20 minutos
VALOR_HORA_FACTOR = 182      # Horas mensuales promedio (42h semanales / 6 días)
INICIO_NOCTURNO = 19         # 7:00 PM
LISTA_TURNOS = ["AM", "PM", "Noche"]

# Configuración de horas nocturnas por turno (Post-19:00)
# PM: 13:30 a 21:30 -> tiene 2.5h nocturnas (19:00 a 21:30)
# Noche: 21:30 a 05:30 -> tiene 8h nocturnas
INFO_TURNOS = {
    "AM": {"nocturnas": 0},
    "PM": {"nocturnas": 2.5},
    "Noche": {"nocturnas": 8}
}

MESES_MAP = {
    "Enero": 1, "Febrero": 2, "Marzo": 3, "Abril": 4, "Mayo": 5, "Junio": 6,
    "Julio": 7, "Agosto": 8, "Septiembre": 9, "Octubre": 10, "Noviembre": 11, "Diciembre": 12
}

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        # Asegurar columnas mínimas
        if 'salario' not in df.columns: df['salario'] = 1300000 
        return df
    except:
        st.warning("No se encontró 'empleados.xlsx'. Cargando datos de prueba.")
        return pd.DataFrame({
            'nombre': ['OPERADOR 1', 'OPERADOR 2', 'MASTER 1'],
            'cargo': ['tecnico A', 'tecnico A', 'master'],
            'descanso': ['domingo', 'domingo', 'sabado'],
            'salario': [1400000, 1400000, 2600000]
        })

df_raw = load_data()

# --- 4. INTERFAZ DE USUARIO ---
with st.sidebar:
    st.title("⚡ MovilGo Pro 2026")
    st.markdown("---")
    ano_sel = st.selectbox("Año", [2026, 2027], index=0)
    mes_sel = st.selectbox("Mes", list(MESES_MAP.keys()), index=datetime.now().month - 1)
    mes_num = MESES_MAP[mes_sel]
    
    st.header("⚖️ Parámetros Reforma")
    r_nocturno = st.number_input("Recargo Nocturno (%)", value=35) / 100
    r_extra = st.number_input("Extra Diurna (%)", value=25) / 100
    r_dominical = st.number_input("Recargo Dominical (%)", value=75) / 100
    
    cargo_sel = st.selectbox("Filtrar por Cargo", sorted(df_raw['cargo'].unique()))
    cupo_manual = st.number_input("Cupo por Turno", 1, 10, 2)

# --- 5. LÓGICA DE OPTIMIZACIÓN Y CÁLCULOS ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_info = []
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    dias_info.append({
        "n": d,
        "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][fecha.weekday()],
        "label": f"{d} - {['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][fecha.weekday()]}"
    })

if st.button("🚀 GENERAR MALLA ÓPTIMA Y AUDITORÍA"):
    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    
    # Modelo Matemático
    prob = LpProblem("Optimizacion_MovilGo", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')
    
    # Función Objetivo: Maximizar cobertura
    prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

    # Restricciones
    for d in range(1, num_dias + 1):
        for t in LISTA_TURNOS:
            prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) <= cupo_manual

    for e in df_f['nombre']:
        # Máximo un turno al día
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
        # Mínimo de días trabajados al mes (aprox 22-24 días)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in LISTA_TURNOS]) >= 20

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        res_list = []
        for d_inf in dias_info:
            for _, row in df_f.iterrows():
                e = row['nombre']
                t_asig = "DISPONIBILIDAD"
                for t in LISTA_TURNOS:
                    if value(asig[e][d_inf["n"]][t]) == 1:
                        t_asig = t
                
                # --- CÁLCULOS DE AUDITORÍA MONETARIA ---
                h_extra = 0; h_noc = 0; costo_dia = 0
                v_hora = row['salario'] / VALOR_HORA_FACTOR
                
                if t_asig in LISTA_TURNOS:
                    h_extra = max(0, 8 - JORNADA_DIARIA_LEGAL) # 8h de turno vs 7.33h ley
                    h_noc = INFO_TURNOS[t_asig]['nocturnas']
                    
                    # Calcular Pesos
                    costo_dia += h_extra * (v_hora * (1 + r_extra))
                    costo_dia += h_noc * (v_hora * r_nocturno)
                    if d_inf["nombre"] == "Dom":
                        costo_dia += 8 * (v_hora * r_dominical)

                res_list.append({
                    "Empleado": e, "Dia": d_inf["label"], "Nom_Dia": d_inf["nombre"],
                    "Turno": t_asig, "H_Extra": h_extra, "H_Nocturnas": h_noc, 
                    "Costo_Recargos": round(costo_dia, 0), "Salario_Base": row['salario']
                })
        
        st.session_state['df_final'] = pd.DataFrame(res_list)
        st.success("✅ Malla generada con éxito aplicando Reforma 2026")

# --- 6. TABS DE RESULTADOS ---
if 'df_final' in st.session_state:
    df_res = st.session_state['df_final']
    t1, t2, t3 = st.tabs(["📅 Malla Operativa", "🔍 Auditoría de Costos", "📈 Resumen Ejecutivo"])

    with t1:
        malla_pivoted = df_res.pivot(index='Empleado', columns='Dia', values='Turno')
        st.dataframe(malla_pivoted, use_container_width=True)

    with t2:
        st.subheader("Cálculo de Recargos y Horas Extra (Ley 2026)")
        resumen_emp = df_res.groupby("Empleado").agg({
            "H_Extra": "sum",
            "H_Nocturnas": "sum",
            "Costo_Recargos": "sum",
            "Salario_Base": "first"
        })
        resumen_emp["Total_a_Pagar"] = resumen_emp["Salario_Base"] + resumen_emp["Costo_Recargos"]
        st.table(resumen_emp.style.format("${:,.0f}"))

    with t3:
        c1, c2, c3 = st.columns(3)
        total_recargos = df_res['Costo_Recargos'].sum()
        c1.metric("Gasto en Recargos/Extras", f"${total_recargos:,.0f}")
        c2.metric("Total Horas Extra", f"{df_res['H_Extra'].sum():.1f} h")
        c3.metric("Jornada Legal", "7h 20min")
        
        st.bar_chart(df_res.groupby("Empleado")["Costo_Recargos"].sum())
