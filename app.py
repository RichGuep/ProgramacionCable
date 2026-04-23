import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo Pro - Sistema Integral", layout="wide", page_icon="🚌")

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h2 style='text-align:center;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True
                    st.rerun()
                else:
                    st.error("Acceso denegado")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_base():
    try:
        # Cargamos el archivo. Asegúrate que se llame exactamente así.
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except Exception as e:
        st.error(f"No se encontró 'empleados.xlsx' o el formato es incorrecto. Error: {e}")
        return None

df_raw = load_base()

if df_raw is not None:
    # --- SIDEBAR GLOBAL ---
    with st.sidebar:
        st.header("📅 Periodo")
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1
        
        st.divider()
        st.header("⚙️ Planta Base")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)

    tab1, tab2 = st.tabs(["🏭 Planta T1-T2-T3", "👥 Auxiliares de Abordaje (10/10)"])

    # --- TAB 1: PLANTA BASE ---
    with tab1:
        st.header("Malla Técnicos y Masters")
        # Aquí se mantiene la lógica de rotación técnica que ya tienes
        st.info("Configura los grupos y presiona generar para esta sección.")

    # --- TAB 2: AUXILIARES DE ABORDAJE Y ATENCIÓN AL PÚBLICO ---
    with tab2:
        st.header("Malla Auxiliares (Cobertura 10 T1 / 10 T2)")
        cargo_buscado = "Auxiliar de Abordaje y Atención al Público"
        df_aux = df_raw[df_raw['cargo'].str.contains(cargo_buscado, case=False, na=False)].copy()
        
        if df_aux.empty:
            st.warning(f"No hay empleados con el cargo: {cargo_buscado}")
        else:
            n_equipos = 5
            per_equipo = 5
            DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
            
            with st.expander("📅 Configurar Descansos de Equipos", expanded=True):
                aux_n_map, aux_d_map = {}, {}
                cols = st.columns(n_equipos)
                for i in range(n_equipos):
                    with cols[i]:
                        n_eq = st.text_input(f"Grupo {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                        d_eq = st.selectbox(f"Descanso", DIAS_SEMANA, index=i%7, key=f"ax_d_{i}")
                        aux_n_map[i] = n_eq
                        aux_d_map[n_eq] = d_eq

            if st.button("⚡ GENERAR MALLA AUXILIARES"):
                df_aux = df_aux.reset_index(drop=True)
                df_aux['equipo'] = [aux_n_map[i // per_equipo] for i in range(len(df_aux))]
                
                num_dias = calendar.monthrange(ano_sel, mes_num)[1]
                d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
                semanas = sorted(list(set([d["sem"] for d in d_info])))
                
                rows_aux = []
                for s_idx, sem in enumerate(semanas):
                    # Lógica 10/10 (2 equipos T1, 2 equipos T2, 1 Disp)
                    pool = ["T1", "T1", "T2", "T2", "DISPONIBILIDAD"]
                    desplazamiento = s_idx % 5
                    turnos_semana = pool[-desplazamiento:] + pool[:-desplazamiento]
                    
                    for d_i in [d for d in d_info if d["sem"] == sem]:
                        for eq_idx in range(n_equipos):
                            eq_name = aux_n_map[eq_idx]
                            t_base = turnos_semana[eq_idx]
                            
                            final_t = t_base
                            if d_i["nom"] == aux_d_map[eq_name]:
                                final_t = "DESC. LEY"
                            
                            for _, emp in df_aux[df_aux['equipo'] == eq_name].iterrows():
                                rows_aux.append({
                                    "Equipo": eq_name, "Empleado": emp['nombre'], "Label": d_i["label"],
                                    "Turno": final_t, "Día": d_i["n"]
                                })
                
                df_f_aux = pd.DataFrame(rows_aux)
                piv_aux = df_f_aux.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                cols_ord = sorted(piv_aux.columns, key=lambda x: int(x.split('-')[0]))

                # --- CORRECCIÓN DEL ERROR DE ATRIBUTO ---
                def estilo_aux(v):
                    v_str = str(v)
                    if v_str == "T1": return 'background-color: #dcfce7; color: #166534; border: 1px solid #b9f6ca'
                    if v_str == "T2": return 'background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd'
                    if "DESC" in v_str: return 'background-color: #EF5350; color: white; font-weight: bold'
                    return 'background-color: #f3f4f6; color: #6b7280; font-style: italic'

                # Usamos .map() en lugar de .applymap() para evitar el AttributeError
                st.subheader("📋 Malla de Auxiliares")
                st.dataframe(piv_aux[cols_ord].style.map(estilo_aux), use_container_width=True)
                
                # Resumen de Cobertura
                st.divider()
                st.subheader("📊 Validación de Cobertura Diaria")
                audit = df_f_aux[df_f_aux['Turno'].isin(["T1", "T2"])].groupby(['Label', 'Turno']).size().unstack().fillna(0)
                st.table(audit.T)
