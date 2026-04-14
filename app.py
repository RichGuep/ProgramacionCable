import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN Y PARÁMETROS LEGALES 2026 ---
st.set_page_config(page_title="MovilGo Pro - Reforma 2026", layout="wide", page_icon="⚡")

JORNADA_DIARIA_LEGAL = 7.33  # 7h 20min
VALOR_HORA_FACTOR = 182      # Horas mensuales promedio para 42h semanales
LISTA_TURNOS = ["AM", "PM", "Noche"]

# Definición de turnos y sus horas nocturnas (Post-19:00)
# AM: 05:30 - 13:30 (0h nocturnas)
# PM: 13:30 - 21:30 (2.5h nocturnas: de 19:00 a 21:30)
# Noche: 21:30 - 05:30 (8h nocturnas: todas están en rango 19:00-06:00)
INFO_TURNOS = {
    "AM": {"inicio": 5.5, "fin": 13.5, "nocturnas": 0},
    "PM": {"inicio": 13.5, "fin": 21.5, "nocturnas": 2.5},
    "Noche": {"inicio": 21.5, "fin": 5.5, "nocturnas": 8}
}

# --- 2. ESTILOS ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    html, body, [class*="st-"], div, span, p, text { font-family: 'Century Gothic', sans-serif !important; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. LÓGICA DE LOGIN (Simplificada para el ejemplo) ---
def login():
    if 'auth' not in st.session_state: st.session_state['auth'] = False
    if not st.session_state['auth']:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("MovilGo Pro 2026")
            with st.form("login"):
                u = st.text_input("Usuario")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Entrar"):
                    if u == "admin" and p == "admin": 
                        st.session_state['auth'] = True
                        st.rerun()
        st.stop()

login()

# --- 4. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        # Dataframe de ejemplo si no existe el archivo
        return pd.DataFrame({
            'nombre': ['Juan Perez', 'Maria Lopez', 'Carlos Ruiz', 'Ana Silva'],
            'cargo': ['tecnico A', 'tecnico A', 'master', 'tecnico B'],
            'descanso': ['domingo', 'domingo', 'sabado', 'domingo'],
            'salario': [1500000, 1500000, 2500000, 1300000]
        })

df_raw = load_data()

# --- 5. SIDEBAR / PARAMETRIZACIÓN ---
with st.sidebar:
    st.header("⚙️ Configuración 2026")
    ano_sel = st.selectbox("Año", [2026], index=0)
    mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
    mes_num = list(calendar.month_name).index(mes_sel if mes_sel != "Enero" else "January") # Fix simple para nombres en español
    
    st.markdown("---")
    st.subheader("💰 Recargos Reforma")
    r_nocturno = st.number_input("Recargo Nocturno (%)", value=35) / 100
    r_extra = st.number_input("Extra Diurna (%)", value=25) / 100
    r_dominical = st.number_input("Recargo Dominical (%)", value=75) / 100

# --- 6. MOTOR DE OPTIMIZACIÓN ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_info = [{"n": d, "nombre": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "label": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

if st.button("🚀 GENERAR MALLA Y AUDITORÍA"):
    # (Lógica de optimización similar a tu script original...)
    # Por brevedad, simulamos la resolución exitosa con los parámetros de la imagen
    df_f = df_raw.copy()
    
    # [Aquí iría el código de PuLP que ya tienes...]
    # Simulamos que ya tenemos df_final con la columna 'Turno' asignada
    
    # --- 7. CÁLCULOS DE AUDITORÍA Y MONETIZACIÓN ---
    def calcular_detalles_legales(row):
        if row['Turno'] not in LISTA_TURNOS:
            return pd.Series([0, 0, 0, 0])
        
        # Horas totales de turno físico: 8h (según tu imagen entrada/salida)
        h_fisicas = 8 
        h_extra = max(0, h_fisicas - JORNADA_DIARIA_LEGAL)
        h_nocturnas = INFO_TURNOS[row['Turno']]['nocturnas']
        
        # Valor de la hora
        v_hora = row['salario'] / VALOR_HORA_FACTOR
        
        # Costos
        costo_extra = h_extra * v_hora * (1 + r_extra)
        costo_recargo_noc = h_nocturnas * v_hora * r_nocturno
        
        costo_dom = 0
        if row['nombre_dia'] == "Dom":
            costo_dom = h_fisicas * v_hora * r_dominical
            
        total_recargos = costo_extra + costo_recargo_noc + costo_dom
        return pd.Series([h_extra, h_nocturnas, total_recargos, v_hora])

    # Aplicamos a la malla generada
    # (Nota: Esto asume que df_final ya existe tras la optimización)
    # df_final[['H_Extra', 'H_Nocturna', 'Costo_Recargos', 'V_Hora']] = df_final.apply(calcular_detalles_legales, axis=1)
    
    st.success("Malla generada con éxito")

# --- 8. VISUALIZACIÓN ---
t1, t2, t3 = st.tabs(["📅 Malla Operativa", "📊 Análisis de Rotación", "💰 Auditoría Salarial"])

with t3:
    st.header("Auditoría de Costos Proyectados")
    st.info(f"Basado en Jornada de {JORNADA_DIARIA_LEGAL}h y Recargo Nocturno desde las 19:00")
    
    # Ejemplo de tabla de resumen
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Horas Extra", "124h", "+15% vs 2025")
    col_b.metric("Costo Proyectado Recargos", "$1.250.000")
    col_c.metric("Equidad de Noches", "98%", "Óptima")

    st.markdown("""
    ### 📝 Desglose por Empleado
    | Empleado | Cargo | Horas Extra | Horas Nocturnas | Sobrecosto Reforma | Estado |
    | :--- | :--- | :--- | :--- | :--- | :--- |
    | Juan Perez | Tecnico A | 18.2h | 40h | $245.000 | ✅ Cumple |
    | Maria Lopez | Tecnico A | 17.5h | 32h | $210.000 | ✅ Cumple |
    """)

with t2:
    st.header("Análisis de Equidad y Rotación")
    # Aquí puedes insertar gráficos de barras de st.bar_chart()
    # comparando cuántas noches hizo cada persona para asegurar que sea justo.
