import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN Y ESTADOS ---
st.set_page_config(page_title="MovilGo Pro - Green Móvil", layout="wide", page_icon="🟢")

# Parámetros iniciales según Manual Funcional [cite: 5, 27]
if 'config_ley' not in st.session_state:
    st.session_state['config_ley'] = {
        "jornada_legal": 7.33,   # 07:20:00 
        "divisor_mes": 182,      # Base 42h/sem [cite: 405]
        "inicio_noche": 19,      # Nocturna desde 19:00 
        "r_nocturno": 0.35,      # +35% 
        "r_extra_diurna": 0.25,  # +125% total [cite: 76]
        "r_extra_nocturna": 0.75, # +175% total [cite: 73]
        "r_dominical_r10": 0.75  # Recargo R10 base [cite: 85]
    }

if 'df_final' not in st.session_state: st.session_state['df_final'] = None

# --- 2. CARGA DE DATOS ---
def load_data():
    if os.path.exists("empleados.xlsx"):
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c), 'nombre')
        c_des = next((c for c in df.columns if 'des' in c), 'descanso')
        c_sal = next((c for c in df.columns if 'sal' in c), 'salario')
        c_car = next((c for c in df.columns if 'car' in c), 'cargo')
        return df.rename(columns={c_nom: 'nombre', c_des: 'descanso_ley', c_sal: 'salario_base', c_car: 'cargo'})
    return None

if st.session_state['df_master'] is None:
    st.session_state['df_master'] = load_data()

# --- 3. ESTILOS DE MALLA ---
def color_turnos(val):
    if val == "---": return 'background-color: #f8f9fa; color: #adb5bd'
    if "Noche" in str(val): return 'background-color: #1a365d; color: white'
    if "PM" in str(val): return 'background-color: #fff3cd; color: #856404'
    if "AM" in str(val): return 'background-color: #d4edda; color: #155724'
    if "Descanso" in str(val): return 'background-color: #f8d7da; color: #721c24'
    return ''

# --- 4. NAVEGACIÓN ---
with st.sidebar:
    st.title("🟢 Green Móvil")
    menu = st.radio("MENÚ PRINCIPAL", ["⚙️ Parametrización", "📅 Programación", "🔄 Rotación", "💰 Finanzas"])

conf = st.session_state['config_ley'] # Definición global para evitar NameError

# --- MÓDULO: PARAMETRIZACIÓN ---
if menu == "⚙️ Parametrización":
    st.header("⚙️ Configuración de Reglas y Salarios")
    t1, t2 = st.tabs(["👥 Personal", "⚖️ Reglas de Liquidación"])
    with t1:
        if st.session_state['df_master'] is not None:
            edited = st.data_editor(st.session_state['df_master'], use_container_width=True)
            if st.button("💾 Guardar Cambios"):
                edited.to_excel("empleados.xlsx", index=False)
                st.session_state['df_master'] = edited
                st.success("Excel actualizado.")
    with t2:
        c1, c2 = st.columns(2)
        with c1:
            conf['inicio_noche'] = st.number_input("Inicio Nocturna (Hora)", 0, 23, conf['inicio_noche'])
            conf['jornada_legal'] = st.number_input("Work Time (7.33 = 7h20m)", 0.0, 10.0, conf['jornada_legal'])
        with c2:
            conf['r_nocturno'] = st.number_input("Recargo Nocturno (%)", 0, 100, 35) / 100
            st.info(f"Regla actual: Horas después de las {conf['inicio_noche']}:00 son nocturnas.")

# --- MÓDULO: PROGRAMACIÓN ---
elif menu == "📅 Programación":
    st.header("📅 Generar Malla de Turnos")
    df_m = st.session_state['df_master']
    if df_m is not None:
        col1, col2, col3 = st.columns(3)
        with col1: mes_sel = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], index=datetime.now().month - 1)
        with col2: cargo_sel = st.selectbox("Cargo", sorted(df_m['cargo'].unique()))
        with col3: cupos = st.number_input("Técnicos por Turno", 1, 10, 2)

        if st.button("🚀 CALCULAR OPTIMIZACIÓN"):
            mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
            df_f = df_m[df_m['cargo'] == cargo_sel].copy()
            num_dias = calendar.monthrange(2026, mes_num)[1]
            dias_info = [{"n": d, "nom": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(2026, mes_num, d).weekday()], "label": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(2026, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

            prob = LpProblem("Green_Movil", LpMaximize)
            asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), ["AM", "PM", "Noche"]), cat='Binary')
            prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in ["AM", "PM", "Noche"]])

            # Restricciones de ley y rotación [cite: 172, 186]
            for e in df_f['nombre']:
                row_e = df_f[df_f['nombre'] == e].iloc[0]
                dia_l = "Sab" if "sab" in str(row_e['descanso_ley']).lower() else "Dom"
                for d in range(1, num_dias + 1):
                    prob += lpSum([asig[e][d][t] for t in ["AM", "PM", "Noche"]]) <= 1
                criticos = [di["n"] for di in dias_info if di["nom"] == dia_l]
                prob += lpSum([asig[e][d][t] for d in criticos for t in ["AM", "PM", "Noche"]]) <= (len(criticos) - 2)

            for d in range(1, num_dias + 1):
                for t in ["AM", "PM", "Noche"]:
                    prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) <= cupos

            prob.solve(PULP_CBC_CMD(msg=0))

            res = []
            for _, re in df_f.iterrows():
                v_hora = re['salario_base'] / conf['divisor_mes']
                for di in dias_info:
                    ta = "---"
                    for t in ["AM", "PM", "Noche"]:
                        if value(asig[re['nombre']][di["n"]][t]) == 1: ta = t
                    
                    costo = 0; he = 0; hn = 0
                    if ta != "---":
                        he = max(0, 8 - conf['jornada_legal']) # Cálculo de extras sobre work time [cite: 25]
                        if ta == "PM": hn = 2.5 # Recargo desde las 19:00 hasta las 21:30 
                        elif ta == "Noche": hn = 8 
                        costo += (he * v_hora * 1.25) + (hn * v_hora * conf['r_nocturno'])

                    res.append({"nombre": re['nombre'], "label": di["label"], "nom_dia": di["nom"], "turno": ta, "salario": re['salario_base'], "costo_extra": costo, "h_extra": he})
            
            st.session_state['df_final'] = pd.DataFrame(res)
            st.success("✅ Programación generada. Desliza hacia abajo para ver la malla.")
            st.dataframe(st.session_state['df_final'].pivot(index='nombre', columns='label', values='turno').style.map(color_turnos), use_container_width=True)

# --- MÓDULO: ROTACIÓN ---
elif menu == "🔄 Rotación":
    st.header("🔄 Visualización de Descansos")
    if st.session_state['df_final'] is not None:
        st.dataframe(st.session_state['df_final'].pivot(index='nombre', columns='label', values='turno').style.map(color_turnos), use_container_width=True)
    else: st.info("Calcule la programación primero.")

# --- MÓDULO: FINANZAS ---
elif menu == "💰 Finanzas":
    st.header("💰 Auditoría Monetaria")
    if st.session_state['df_final'] is not None:
        df_a = st.session_state['df_final']
        resumen = df_a.groupby("nombre").agg({"salario": "first", "h_extra": "sum", "costo_extra": "sum"})
        resumen["Total"] = resumen["salario"] + resumen["costo_extra"]
        st.table(resumen.style.format("${:,.0f}"))
