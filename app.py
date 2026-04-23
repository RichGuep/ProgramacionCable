import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Lógica Blindada", layout="wide", page_icon="🛡️")
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

# --- 3. CARGA Y PROCESAMIENTO ---
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

    num_mas = len(df_raw[df_raw['cargo'].str.contains('Master', case=False)])
    num_tca = len(df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)])
    num_tcb = len(df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)])
    num_g = min(num_mas//m_req if m_req>0 else 99, num_tca//ta_req if ta_req>0 else 99, num_tcb//tb_req if tb_req>0 else 99)

    st.title(f"🔄 Malla: Rotación Estricta Post-Descanso")
    
    with st.expander("📅 Configuración de Descansos", expanded=True):
        n_map, d_map = {}, {}
        cols = st.columns(num_g if num_g > 0 else 1)
        for i in range(num_g):
            with cols[i]:
                n_s = st.text_input(f"G{i+1}", f"GRUPO {i+1}", key=f"n_{i}")
                d_s = st.selectbox(f"Descanso", DIAS_SEMANA, index=i % 7, key=f"d_{i}")
                n_map[f"G{i+1}"] = n_s
                d_map[n_s] = d_s

    # Armado de grupos
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

    if st.button("⚡ GENERAR MALLA (BLOQUEO POST-DESCANSO)"):
        # Optimizamos solo los turnos base por semana calendario
        prob = LpProblem("MovilGo_Core", LpMinimize)
        asig = LpVariable.dicts("Asig", (g_finales, semanas, LISTA_TURNOS), cat='Binary')
        prob += lpSum([ (1 - asig[g][s][t]) for g in g_finales for s in semanas for t in LISTA_TURNOS])
        
        for s in semanas:
            for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_finales]) >= 1
            for g in g_finales: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) <= 1
        
        for g in g_finales:
            for i in range(len(semanas)-1):
                s1, s2 = semanas[i], semanas[i+1]
                prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"] # PM -> Noche
                prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"] # Noche -> AM
                prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"] # AM -> PM
        
        prob.solve(PULP_CBC_CMD(msg=0))

        # Turnos base teóricos
        res_semanal = {(g, s): t for g in g_finales for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}

        # --- CONSTRUCCIÓN DÍA A DÍA CON LÓGICA DE ARRASTRE ---
        final_rows = []
        # Diccionario para recordar el turno "vivo" de cada grupo
        turno_vivo = {g: res_semanal.get((g, semanas[0]), "T1") for g in g_finales}

        for d_i in d_info:
            dia_actual_str = d_i["nom"]
            # 1. Identificar quién descansa hoy
            descansan_hoy = [g for g in g_finales if d_map[g] == dia_actual_str]
            # 2. Identificar el grupo de apoyo (el que no tiene turno asignado o el extra)
            # Para este ejemplo, si hay un grupo "Disponible", será el que cubra.
            
            asignaciones_hoy = {}
            for g in g_finales:
                es_descanso = (dia_actual_str == d_map[g])
                
                if es_descanso:
                    asignaciones_hoy[g] = "DESC. LEY"
                    # CRÍTICO: Al final de este día (después del descanso), 
                    # el turno vivo cambia al que corresponde a esta semana calendario
                    turno_vivo[g] = res_semanal.get((g, d_i["sem"]), turno_vivo[g])
                else:
                    asignaciones_hoy[g] = turno_vivo[g]

            # 3. Lógica de Apoyo: Si un grupo está marcado como "APOYO" (ej. Grupo 4)
            # debe cubrir el turno que dejó el que está en DESC. LEY
            for g in g_finales:
                res_final = asignaciones_hoy[g]
                
                # Si el grupo actual es el de apoyo (puedes definirlo por nombre o por lógica)
                # Aquí asumimos que el Grupo 4 es apoyo si no está en el ciclo principal
                if "GRUPO 4" in g and res_final != "DESC. LEY":
                    for g_descanso in descansan_hoy:
                        # El de apoyo toma el turno que venía haciendo el que descansó
                        turno_a_cubrir = turno_vivo[g_descanso]
                        res_final = f"{turno_a_cubrir} (Apoyo G{g_descanso[-1]})"
                        break

                miembros = df_celulas[df_celulas['grupo'] == g]
                for _, m in miembros.iterrows():
                    final_rows.append({
                        "Dia": d_i["n"], "Label": d_i["label"], "Empleado": m['nombre'], 
                        "Cargo": m['cargo'], "Grupo": g, "Final": res_final
                    })

        st.session_state['malla_final'] = pd.DataFrame(final_rows)

    if 'malla_final' in st.session_state:
        df_f = st.session_state['malla_final']
        piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
        cols_ordenadas = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
        piv = piv[cols_ordenadas]

        def aplicar_estilos(row):
            g_actual = row.name[0]
            colores = {g_finales[0]: "#E3F2FD", g_finales[1] if len(g_finales)>1 else "N": "#F1F8E9", g_finales[2] if len(g_finales)>2 else "N": "#FFF3E0", g_finales[3] if len(g_finales)>3 else "N": "#F3E5F5"}
            textos = {g_finales[0]: "#1565C0", g_finales[1] if len(g_finales)>1 else "N": "#2E7D32", g_finales[2] if len(g_finales)>2 else "N": "#EF6C00", g_finales[3] if len(g_finales)>3 else "N": "#7B1FA2"}
            estilos = []
            for val in row:
                v = str(val)
                if 'DESC' in v: estilos.append('background-color: #EF5350; color: white; font-weight: bold')
                elif 'Apoyo' in v: estilos.append(f'background-color: white; color: {textos.get(g_actual)}; border: 2px dashed {textos.get(g_actual)}; font-size: 0.85em')
                elif 'T3' in v: estilos.append('background-color: #263238; color: white; font-weight: bold')
                elif 'T1' in v: estilos.append(f'background-color: {colores.get(g_actual)}; color: {textos.get(g_actual)}; border: 1px solid #166534')
                elif 'T2' in v: estilos.append(f'background-color: {colores.get(g_actual)}; color: {textos.get(g_actual)}; border: 1px solid #0369a1')
                else: estilos.append('color: gray')
            return estilos

        st.dataframe(piv.style.apply(aplicar_estilos, axis=1), use_container_width=True)
