import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import os

# --- 1. CONFIGURACIÓN ESTRATÉGICA ---
st.set_page_config(page_title="MovilGo Pro - Green Móvil", layout="wide", page_icon="🟢")

# Inicialización de parámetros globales en el estado de la sesión
if 'config_ley' not in st.session_state:
    st.session_state['config_ley'] = {
        "jornada_legal": 7.33,   # 7h 20min (Reforma 2026)
        "divisor_mes": 182,      # Base para 42h semanales
        "inicio_noche": 19,      # Recargo nocturno desde las 19:00 según manual
        "r_nocturno": 0.35,      # +35%
        "r_extra_diurna": 0.25,  # +25% (total 125%)
        "r_dominical": 0.75      # +75% (para R10 es mayor, ajustado en el cálculo)
    }

if 'df_final' not in st.session_state:
    st.session_state['df_final'] = None

# --- 2. GESTIÓN DE DATOS ---
def load_data():
    if os.path.exists("empleados.xlsx"):
        try:
            df = pd.read_excel("empleados.xlsx")
            df.columns = df.columns.str.strip().str.lower()
            # Normalización de nombres de columnas
            c_des = next((c for c in df.columns if 'des' in c), "descanso_ley")
            c_sal = next((c for c in df.columns if 'sal' in c), "salario_base")
            return df.rename(columns={c_des: 'descanso_ley', c_sal: 'salario_base'})
        except Exception as e:
            st.error(f"Error al leer Excel: {e}")
    return None

if 'df_master' not in st.session_state:
    st.session_state['df_master'] = load_data()

# --- 3. MENÚ DE NAVEGACIÓN MODULAR ---
with st.sidebar:
    st.title("🟢 Green Móvil")
    menu = st.radio("MENÚ PRINCIPAL", 
        ["⚙️ Parametrización", "📅 Generar Programación", "🔄 Control de Rotación", "💰 Auditoría Monetaria"])
    st.markdown("---")
    st.caption(f"Versión 4.4 - Noche desde las {st.session_state['config_ley']['inicio_noche']}:00")

# --- MÓDULO 1: PARAMETRIZACIÓN ---
if menu == "⚙️ Parametrización":
    st.header("⚙️ Configuración del Sistema")
    t1, t2 = st.tabs(["👥 Personal y Salarios", "⚖️ Tasas y Horarios"])
    
    with t1:
        if st.session_state['df_master'] is not None:
            edited_df = st.data_editor(st.session_state['df_master'], use_container_width=True, num_rows="dynamic")
            if st.button("💾 Guardar Personal en Excel"):
                edited_df.to_excel("empleados.xlsx", index=False)
                st.session_state['df_master'] = edited_df
                st.success("Archivo 'empleados.xlsx' actualizado.")
    
    with t2:
        conf = st.session_state['config_ley']
        col1, col2 = st.columns(2)
        with col1:
            conf['inicio_noche'] = st.number_input("Inicio Franja Nocturna (Hora)", 0, 23, conf['inicio_noche'])
            conf['jornada_legal'] = st.number_input("Jornada Legal (Horas/Día)", 0.0, 10.0, conf['jornada_legal'])
        with col2:
            conf['r_nocturno'] = st.number_input("Recargo Nocturno (%)", 0, 100, int(conf['r_nocturno']*100)) / 100
            conf['r_dominical'] = st.number_input("Recargo Dominical Básico (%)", 0, 100, int(conf['r_dominical']*100)) / 100
        st.info("Estos valores afectan directamente el cálculo de la nómina y la generación de turnos.")

# --- MÓDULO 2: GENERAR PROGRAMACIÓN (MOTOR PULP) ---
elif menu == "📅 Generar Programación":
    st.header("📅 Motor de Optimización de Turnos")
    
    if st.session_state['df_master'] is not None:
        df_raw = st.session_state['df_master']
        col1, col2, col3 = st.columns(3)
        with col1:
            mes_sel = st.selectbox("Mes a programar", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
            mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
        with col2:
            cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        with col3:
            cupo_manual = st.number_input("Técnicos por Turno", 1, 15, 2)

        if st.button("🚀 GENERAR MALLA ÓPTIMA"):
            df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
            num_dias = calendar.monthrange(2026, mes_num)[1]
            dias_info = [{"n": d, "nom": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(2026, mes_num, d).weekday()], "label": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(2026, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]

            prob = LpProblem("MovilGo_Green", LpMaximize)
            LISTA_TURNOS = ["AM", "PM", "Noche"]
            asig = LpVariable.dicts("Asig", (df_f['nombre'], range(1, num_dias + 1), LISTA_TURNOS), cat='Binary')

            prob += lpSum([asig[e][d][t] for e in df_f['nombre'] for d in range(1, num_dias + 1) for t in LISTA_TURNOS])

            for e in df_f['nombre']:
                row_e = df_f[df_f['nombre'] == e].iloc[0]
                dia_ley_nom = "Sab" if "sab" in str(row_e['descanso_ley']).lower() else "Dom"
                for d in range(1, num_dias + 1):
                    prob += lpSum([asig[e][d][t] for t in LISTA_TURNOS]) <= 1
                    if d < num_dias:
                        prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 0 # Higiene sueño estricta
                        prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                dias_criticos = [di["n"] for di in dias_info if di["nom"] == dia_ley_nom]
                prob += lpSum([asig[e][d][t] for d in dias_criticos for t in LISTA_TURNOS]) <= (len(dias_criticos) - 2)

            for d in range(1, num_dias + 1):
                for t in LISTA_TURNOS:
                    prob += lpSum([asig[e][d][t] for e in df_f['nombre']]) <= cupo_manual

            prob.solve(PULP_CBC_CMD(msg=0))

            # --- PROCESAMIENTO CON REGLAS DE GREEN MÓVIL ---
            conf = st.session_state['config_ley']
            final_rows = []
            for _, row_e in df_f.iterrows():
                v_hora = row_e['salario_base'] / conf['divisor_mes']
                for di in dias_info:
                    t_asig = "---"
                    for t in LISTA_TURNOS:
                        if value(asig[row_e['nombre']][di["n"]][t]) == 1: t_asig = t
                    
                    h_extra = 0; h_noc = 0; costo_r = 0
                    if t_asig in LISTA_TURNOS:
                        h_extra = 8 - conf['jornada_legal']
                        # Cálculo de nocturnas según el manual (PM tiene recargo desde inicio_noche)
                        if t_asig == "PM": h_noc = 21.5 - conf['inicio_noche'] if 21.5 > conf['inicio_noche'] else 0
                        elif t_asig == "Noche": h_noc = 8 
                        
                        costo_r += h_extra * (v_hora * 1.25)
                        costo_r += h_noc * (v_hora * conf['r_nocturno'])
                        if di["nom"] == ("Sab" if "sab" in str(row_e['descanso_ley']).lower() else "Dom"):
                            costo_r += 8 * (v_hora * 0.75) # Recargo por trabajar día de ley

                    final_rows.append({
                        "Empleado": row_e['nombre'], "Label": di["label"], "Nom_Dia": di["nom"], "Dia": di["n"],
                        "Turno": t_asig, "Salario": row_e['salario_base'], "V_Hora": v_hora, "Costo_R": costo_r,
                        "H_Extra": h_extra if t_asig != "---" else 0, "H_Noc": h_noc
                    })
            
            st.session_state['df_final'] = pd.DataFrame(final_rows)
            st.success("✅ Malla generada satisfactoriamente.")
    else:
        st.error("Cargue el archivo 'empleados.xlsx' para comenzar.")

# --- MÓDULO 3: CONTROL DE ROTACIÓN ---
elif menu == "🔄 Control de Rotación":
    st.header("🔄 Visualización de Descansos")
    if st.session_state['df_final'] is not None:
        df_v = st.session_state['df_final']
        m_piv = df_v.pivot(index='Empleado', columns='Label', values='Turno')
        
        # Lógica de colores para visualizar descansos
        def color_map(val):
            if val == "---": return 'background-color: #ffcccc; color: #b30000' # Disponibilidad/Descanso
            return ''
        
        st.dataframe(m_piv.style.applymap(color_map), use_container_width=True)
        st.info("💡 Las celdas en rojo representan días de descanso o disponibilidad.")
    else:
        st.warning("Primero debe generar la programación en el módulo anterior.")

# --- MÓDULO 4: AUDITORÍA MONETARIA ---
elif menu == "💰 Auditoría Monetaria":
    st.header("💰 Liquidación Proyectada 2026")
    if st.session_state['df_final'] is not None:
        df_a = st.session_state['df_final']
        resumen = df_a.groupby("Empleado").agg({
            "Salario": "first", "H_Extra": "sum", "H_Noc": "sum", "Costo_R": "sum"
        })
        resumen["Total Nómina"] = resumen["Salario"] + resumen["Costo_R"]
        
        st.subheader("Resumen por Empleado")
        st.table(resumen.style.format("${:,.0f}", subset=["Salario", "Costo_R", "Total Nómina"]))
        
        col1, col2 = st.columns(2)
        col1.metric("Gasto Total Nómina", f"${resumen['Total Nómina'].sum():,.0f}")
        col2.metric("Total Recargos/Extras", f"${resumen['Costo_R'].sum():,.0f}")
    else:
        st.warning("No hay datos para auditar. Genere la programación.")
