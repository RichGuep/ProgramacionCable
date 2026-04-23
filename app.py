import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Visual por Grupos", layout="wide", page_icon="🎨")
LISTA_TURNOS = ["T1", "T2", "T3"] 

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo Admin</h1>", unsafe_allow_html=True)
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
        st.header("⚙️ Configuración")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1

    def obtener_cantidad_grupos(df, m, ta, tb):
        mas = len(df[df['cargo'].str.contains('Master', case=False, na=False)])
        tca = len(df[df['cargo'].str.contains('Tecnico A', case=False, na=False)])
        tcb = len(df[df['cargo'].str.contains('Tecnico B', case=False, na=False)])
        return min(mas//m if m>0 else 99, tca//ta if ta>0 else 99, tcb//tb if tb>0 else 99)

    num_g = obtener_cantidad_grupos(df_raw, m_req, ta_req, tb_req)

    st.title(f"🎨 Programación por Células: {mes_sel}")
    
    with st.expander("🏷️ Personalización de Grupos", expanded=True):
        n_map, d_map = {}, {}
        cols = st.columns(num_g if num_g > 0 else 1)
        for i in range(num_g):
            with cols[i]:
                n_s = st.text_input(f"G{i+1}", f"GRUPO {i+1}", key=f"n_{i}")
                d_s = st.selectbox(f"Ley {n_s}", ["Lunes", "Viernes", "Sabado", "Domingo"], index=i % 4, key=f"d_{i}")
                n_map[f"G{i+1}"] = n_s
                d_map[n_s] = d_s

    # Armado de personal
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

    # Motor de Optimización (Lógica T3 Bloqueo + Ciclo)
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = [{"n": d, "nom": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "lab": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][datetime(ano_sel, mes_num, d).weekday()]}"} for d in range(1, num_dias + 1)]
    semanas = sorted(list(set([d["sem"] for d in d_info])))

    if st.button("⚡ GENERAR MALLA COLORIZADA"):
        prob = LpProblem("MovilGo_Color", LpMaximize)
        asig = LpVariable.dicts("Asig", (g_finales, semanas, LISTA_TURNOS), cat='Binary')
        prob += lpSum([asig[g][s][t] for g in g_finales for s in semanas for t in LISTA_TURNOS])
        for s in semanas:
            for t in LISTA_TURNOS: prob += lpSum([asig[g][s][t] for g in g_finales]) >= 1
            for g in g_finales: prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) <= 1
        for g in g_finales:
            for i in range(len(semanas)-1):
                s1, s2 = semanas[i], semanas[i+1]
                prob += asig[g][s1]["T3"] + asig[g][s2]["T1"] <= 1 # Bloqueo fatiga
                prob += asig[g][s1]["T3"] <= asig[g][s2]["T2"]
                prob += asig[g][s1]["T2"] <= asig[g][s2]["T1"]
        prob.solve(PULP_CBC_CMD(msg=0))

        res_map = {}
        for s in semanas:
            for t in LISTA_TURNOS:
                enc = False
                for g in g_finales:
                    if value(asig[g][s][t]) == 1:
                        if not enc: res_map[(g, s)] = t; enc = True
                        else: res_map[(g, s)] = f"{t} DISPO"

        final_rows = []
        for d_i in d_info:
            for g in g_finales:
                t_f = res_map.get((g, d_i["sem"]), "DISPONIBLE")
                es_l = (d_i["nom"] == d_map[g][:3])
                for _, m in df_celulas[df_celulas['grupo'] == g].iterrows():
                    final_rows.append({"Dia": d_i["n"], "Label": d_i["lab"], "Nom_Dia": d_i["nom"], "Semana": d_i["sem"], "Empleado": m['nombre'], "Cargo": m['cargo'], "Grupo": g, "Turno": t_f, "Ley": es_l})

        df_res = pd.DataFrame(final_rows)
        p_rows = []
        for _, g_emp in df_res.groupby("Empleado"):
            g_emp = g_emp.sort_values("Dia").copy()
            deuda = False
            for s in semanas:
                f_s = g_emp[g_emp['Semana'] == s]
                t_s = str(f_s['Turno'].iloc[0])
                if "T3" in t_s and d_map[g_emp['Grupo'].iloc[0]] in ["Viernes", "Sabado"]:
                    g_emp.loc[f_s.index, 'Final'] = t_s; deuda = True
                else:
                    g_emp.loc[f_s.index, 'Final'] = t_s
                    if deuda:
                        idx_c = f_s[f_s['Nom_Dia'] == 'Mar'].index
                        if not idx_c.empty: g_emp.loc[idx_c, 'Final'] = "DESC. COMPENSATORIO"; deuda = False
                    idx_l = f_s[f_s['Ley']].index
                    if not idx_l.empty: g_emp.loc[idx_l, 'Final'] = "DESC. LEY"
            p_rows.append(g_emp)

        st.session_state['malla_final'] = pd.concat(p_rows)

    if 'malla_final' in st.session_state:
        df_f = st.session_state['malla_final']
        piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
        
        # --- LÓGICA DE COLORES POR GRUPO ---
        def aplicar_estilos(row):
            # Colores base para cada grupo
            colores_grupos = {
                g_finales[0]: "#E3F2FD", # Azul muy claro
                g_finales[1] if len(g_finales)>1 else "": "#F1F8E9", # Verde muy claro
                g_finales[2] if len(g_finales)>2 else "": "#FFF3E0", # Naranja muy claro
                g_finales[3] if len(g_finales)>3 else "": "#F3E5F5", # Morado muy claro
            }
            texto_grupos = {
                g_finales[0]: "#1565C0", 
                g_finales[1] if len(g_finales)>1 else "": "#2E7D32", 
                g_finales[2] if len(g_finales)>2 else "": "#EF6C00",
                g_finales[3] if len(g_finales)>3 else "": "#7B1FA2",
            }
            
            grupo_actual = row.name[0]
            estilos = []
            for val in row:
                if 'DESC' in str(val):
                    estilos.append('background-color: #EF5350; color: white; font-weight: bold; border: 1px solid white') # Rojo Descanso
                elif 'DISPO' in str(val) and val != 'DISPONIBLE':
                    estilos.append(f'background-color: {colores_grupos.get(grupo_actual, "#fff")}; color: {texto_grupos.get(grupo_actual, "#000")}; border: 2px dashed {texto_grupos.get(grupo_actual, "#000")}')
                elif val == 'T3':
                    estilos.append('background-color: #263238; color: white; font-weight: bold') # Negro para Noche siempre
                else:
                    estilos.append(f'background-color: {colores_grupos.get(grupo_actual, "#fff")}; color: {texto_grupos.get(grupo_actual, "#000")}; border: 1px solid #e0e0e0')
            return estilos

        st.subheader("📅 Malla Operativa por Células")
        st.dataframe(piv.style.apply(aplicar_estilos, axis=1), use_container_width=True)
