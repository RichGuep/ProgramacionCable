import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Cobertura Unificada", layout="wide", page_icon="⚙️")
LISTA_TURNOS = ["T1", "T2", "T3"] 
DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h2 style='text-align:center;'>MovilGo Admin</h2>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario"); p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("INGRESAR"):
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'] = True; st.rerun()
                else: st.error("Acceso denegado")
    st.stop()

# --- 3. CARGA DE DATOS ---
@st.cache_data
def load_base():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        return df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
    except: return None

df_raw = load_base()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Parámetros")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1

    num_g = 4 
    st.title(f"🗓️ Planificación Unificada: {mes_sel}")
    
    with st.expander("📅 Configuración de Grupos", expanded=True):
        n_map, d_map, t_map = {}, {}, {}
        cols = st.columns(num_g)
        for i in range(num_g):
            with cols[i]:
                g_id = f"G{i+1}"
                n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_{i}")
                d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_{i}")
                es_disp = st.checkbox("¿Es Disponibilidad?", value=(i==3), key=f"t_{i}")
                n_map[g_id] = n_s
                d_map[n_s] = d_s
                t_map[n_s] = "DISP" if es_disp else "ROTA"

    # Distribución de personal
    mas_p, tca_p, tcb_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy(), df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy(), df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    c_list = []
    for i in range(num_g):
        g_name = n_map[f"G{i+1}"]
        for _ in range(m_req): 
            if not mas_p.empty: c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name}); mas_p = mas_p.iloc[1:]
        for _ in range(ta_req): 
            if not tca_p.empty: c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name}); tca_p = tca_p.iloc[1:]
        for _ in range(tb_req): 
            if not tcb_p.empty: c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name}); tcb_p = tcb_p.iloc[1:]
    df_celulas = pd.DataFrame(c_list)
    g_finales = list(n_map.values())

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = [{"n": d, "nom": DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "label": f"{d:02d}-{DIAS_SEMANA[datetime(ano_sel, mes_num, d).weekday()][:3]}"} for d in range(1, num_dias + 1)]
    semanas = sorted(list(set([d["sem"] for d in d_info])))

    if st.button("⚡ GENERAR MALLA CON COBERTURA IDÉNTICA"):
        # 1. OPTIMIZACIÓN DE TURNOS BASE
        g_rotan = [g for g in g_finales if t_map[g] == "ROTA"]
        prob = LpProblem("MovilGo_Rota", LpMinimize)
        asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
        
        prob += lpSum([ (1 - asig[g][s][t]) for g in g_rotan for s in semanas for t in LISTA_TURNOS])
        for s in semanas:
            for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
            for g in g_rotan: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
        
        for g in g_rotan:
            for i in range(len(semanas)-1):
                s1, s2 = semanas[i], semanas[i+1]
                prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"] 
                prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"] 
                prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"] 
        prob.solve(PULP_CBC_CMD(msg=0))
        res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

        # --- 2. CONSTRUCCIÓN DÍA A DÍA ---
        final_rows = []
        turno_vivo = {g: res_semanal.get((g, semanas[0]), "T1") for g in g_rotan}
        g_disp_list = [g for g in g_finales if t_map[g] == "DISP"]
        g_disp = g_disp_list[0] if g_disp_list else "N/A"
        ultimo_turno_disp = "T1"

        for d_i in d_info:
            dia_nom = d_i["nom"]
            descansan_hoy = [g for g in g_rotan if d_map[g] == dia_nom]
            
            hoy_labels = {}
            for g in g_rotan:
                if dia_nom == d_map[g]:
                    hoy_labels[g] = "DESC. LEY"
                    turno_vivo[g] = res_semanal.get((g, d_i["sem"]), turno_vivo[g])
                else:
                    hoy_labels[g] = turno_vivo[g]
            
            # Lógica para el grupo de DISPONIBILIDAD
            if g_disp != "N/A":
                if dia_nom == d_map[g_disp]:
                    label_disp = "DESC. LEY"
                else:
                    if descansan_hoy:
                        g_a_cubrir = descansan_hoy[0]
                        turno_necesario = turno_vivo[g_a_cubrir]
                        
                        # REGLA DE SALTO: No T2 -> T1 sin descanso
                        if ultimo_turno_disp == "T2" and turno_necesario == "T1":
                            label_disp = "T2" 
                        else:
                            # ASIGNACIÓN IDÉNTICA AL TURNO ORIGINAL
                            label_disp = turno_necesario 
                    else:
                        label_disp = "T1"
                
                if "DESC" not in label_disp: ultimo_turno_disp = label_disp[:2]

            for g in g_finales:
                res_final = label_disp if g == g_disp else hoy_labels[g]
                for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                    final_rows.append({"Dia": d_i["n"], "Label": d_i["label"], "Empleado": m['nombre'], "Cargo": m['cargo'], "Grupo": g, "Final": res_final})

        st.session_state['malla_final'] = pd.DataFrame(final_rows)

    if 'malla_final' in st.session_state:
        df_f = st.session_state['malla_final']
        piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
        cols_ordenadas = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
        piv = piv[cols_ordenadas]

        def aplicar_estilos(row):
            g_actual = row.name[0]
            # Colores base según el grupo para diferenciar visualmente los equipos
            col_map = {g_finales[0]: "#E3F2FD", g_finales[1]: "#F1F8E9", g_finales[2]: "#FFF3E0", g_finales[3]: "#F3E5F5"}
            txt_map = {g_finales[0]: "#1565C0", g_finales[1]: "#2E7D32", g_finales[2]: "#EF6C00", g_finales[3]: "#7B1FA2"}
            
            estilos = []
            for val in row:
                v = str(val)
                # Formato Universal de Descansos
                if 'DESC' in v:
                    estilos.append('background-color: #EF5350; color: white; font-weight: bold')
                # Formato Universal de Noche (T3)
                elif 'T3' == v:
                    estilos.append('background-color: #263238; color: white; font-weight: bold')
                # Formato Universal de AM (T1)
                elif 'T1' in v:
                    estilos.append(f'background-color: {col_map.get(g_actual)}; color: {txt_map.get(g_actual)}; border: 1px solid #166534')
                # Formato Universal de PM (T2)
                elif 'T2' in v:
                    estilos.append(f'background-color: {col_map.get(g_actual)}; color: {txt_map.get(g_actual)}; border: 1px solid #0369a1')
                else:
                    estilos.append('color: gray')
            return estilos

        st.dataframe(piv.style.apply(aplicar_estilos, axis=1), use_container_width=True)
