import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import math

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Control Operativo Total", layout="wide", page_icon="⚡")
LISTA_TURNOS = ["T1", "T2", "T3"] 

# --- 2. LOGIN ---
if 'auth' not in st.session_state: st.session_state['auth'] = False
if not st.session_state['auth']:
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        st.markdown("<h1 style='text-align:center;'>MovilGo Admin</h1>", unsafe_allow_html=True)
        with st.form("Login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
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
        st.header("⚙️ Configuración de Célula")
        m_req = st.number_input("Masters", 1, 5, 2)
        ta_req = st.number_input("Técnicos A", 1, 15, 7)
        tb_req = st.number_input("Técnicos B", 1, 10, 3)
        st.divider()
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        ano_sel = st.selectbox("Año", [2025, 2026], index=1)
        mes_num = meses.index(mes_sel) + 1

    def obtener_cant_g(df, m, ta, tb):
        mas = len(df[df['cargo'].str.contains('Master', case=False, na=False)])
        tca = len(df[df['cargo'].str.contains('Tecnico A', case=False, na=False)])
        tcb = len(df[df['cargo'].str.contains('Tecnico B', case=False, na=False)])
        return min(mas//m if m>0 else 99, tca//ta if ta>0 else 99, tcb//tb if tb>0 else 99)

    num_g = obtener_cant_g(df_raw, m_req, ta_req, tb_req)

    st.title(f"📊 Programación Estratégica: {mes_sel}")
    
    with st.expander("🏷️ Nombres y Descansos de Grupos", expanded=True):
        nombres_map, descansos_map = {}, {}
        cols_cfg = st.columns(num_g if num_g > 0 else 1)
        for i in range(num_g):
            with cols_cfg[i]:
                n_s = st.text_input(f"Nombre G{i+1}", f"GRUPO {i+1}", key=f"n_{i}")
                d_s = st.selectbox(f"Día Ley {n_s}", ["Lunes", "Viernes", "Sabado", "Domingo"], index=i % 4, key=f"d_{i}")
                nombres_map[f"G{i+1}"] = n_s
                descansos_map[n_s] = d_s

    # Armado de personal por célula
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    celulas_list = []
    for i in range(num_g):
        g_name = nombres_map[f"G{i+1}"]
        for _ in range(m_req): 
            if not mas_p.empty: celulas_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name}); mas_p = mas_p.iloc[1:]
        for _ in range(ta_req): 
            if not tca_p.empty: celulas_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name}); tca_p = tca_p.iloc[1:]
        for _ in range(tb_req): 
            if not tcb_p.empty: celulas_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name}); tcb_p = tcb_p.iloc[1:]

    df_celulas = pd.DataFrame(celulas_list)
    g_finales = list(nombres_map.values())

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info = []
    for d in range(1, num_dias + 1):
        dt = datetime(ano_sel, mes_num, d)
        d_info.append({"n": d, "nom": ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"][dt.weekday()], "sem": dt.isocalendar()[1], "lab": f"{d}-{['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom'][dt.weekday()]}"})
    
    semanas_list = sorted(list(set([d["sem"] for d in d_info])))

    if st.button("⚡ GENERAR MALLA Y AUDITORÍA"):
        with st.status("Aplicando bloqueos de seguridad y reglas T3...", expanded=True) as status:
            prob = LpProblem("MovilGo_Final", LpMaximize)
            asig_sem = LpVariable.dicts("AsigSem", (g_finales, semanas_list, LISTA_TURNOS), cat='Binary')
            
            prob += lpSum([asig_sem[g][s][t] for g in g_finales for s in semanas_list for t in LISTA_TURNOS])

            for s in semanas_list:
                for t in LISTA_TURNOS:
                    prob += lpSum([asig_sem[g][s][t] for g in g_finales]) >= 1
                for g in g_finales:
                    prob += lpSum([asig_sem[g][s][t] for t in LISTA_TURNOS]) <= 1

            for g in g_finales:
                for i in range(len(semanas_list)-1):
                    s1, s2 = semanas_list[i], semanas_list[i+1]
                    # Bloqueo T3: No puede pasar a T1/T2 inmediatamente el lunes
                    prob += asig_sem[g][s1]["T3"] + asig_sem[g][s2]["T1"] <= 1
                    # Ciclo T3 -> T2 -> T1
                    prob += asig_sem[g][s1]["T3"] <= asig_sem[g][s2]["T2"]
                    prob += asig_sem[g][s1]["T2"] <= asig_sem[g][s2]["T1"]

            prob.solve(PULP_CBC_CMD(msg=0))

            res_map = {}
            for s in semanas_list:
                for t in LISTA_TURNOS:
                    enc = False
                    for g in g_finales:
                        if value(asig_sem[g][s][t]) == 1:
                            if not enc: res_map[(g, s)] = t; enc = True
                            else: res_map[(g, s)] = f"{t} DISPO"

            final_data = []
            for d_i in d_info:
                for g in g_finales:
                    t_f = res_map.get((g, d_i["sem"]), "DISPONIBILIDAD")
                    es_l = (d_i["nom"] == descansos_map[g][:3])
                    miembros = df_celulas[df_celulas['grupo'] == g]
                    for _, m in miembros.iterrows():
                        final_data.append({"Dia": d_i["n"], "Label": d_i["lab"], "Nom_Dia": d_i["nom"], "Semana": d_i["sem"], 
                                           "Empleado": m['nombre'], "Cargo": m['cargo'], "Grupo": g, "Turno": t_f, "Ley": es_l})

            df_res = pd.DataFrame(final_data)
            p_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                deuda_t3 = False
                for s in semanas_list:
                    f_s = g_emp[g_emp['Semana'] == s]
                    if f_s.empty: continue
                    t_s = str(f_s['Turno'].iloc[0])
                    
                    if "T3" in t_s:
                        # En T3 NO hay descanso Vie/Sab, trabaja de largo
                        g_emp.loc[f_s.index, 'Resultado'] = t_s
                        if descansos_map[g_emp['Grupo'].iloc[0]] in ["Viernes", "Sabado"]:
                            deuda_t3 = True
                    else:
                        g_emp.loc[f_s.index, 'Resultado'] = t_s
                        # Si venía de T3, el lunes/martes es descanso obligatorio antes de T2/T1
                        if deuda_t3:
                            idx_c = f_s[f_s['Nom_Dia'] == 'Mar'].index
                            if not idx_c.empty:
                                g_emp.loc[idx_c, 'Resultado'] = "DESC. COMPENSATORIO"
                                deuda_t3 = False
                        
                        idx_l = f_s[f_s['Ley']].index
                        if not idx_l.empty and "COMP" not in str(g_emp.loc[idx_l, 'Resultado'].values[0]):
                            g_emp.loc[idx_l, 'Resultado'] = "DESC. LEY"
                p_rows.append(g_emp)

            st.session_state['malla_final'] = pd.concat(p_rows)
            status.update(label="✅ Malla generada con éxito.", state="complete")

    if 'malla_final' in st.session_state:
        t1, t2, t3 = st.tabs(["📅 Malla Operativa", "🛡️ Cupos Diarios", "⚖️ Auditoría"])
        df_f = st.session_state['malla_final']
        
        with t1:
            piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Resultado')
            cols = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
            def styler(v):
                if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'COMP' in str(v): return 'background-color: #fef9c3; color: #854d0e; font-weight: bold'
                if 'DISPO' in str(v) and v != 'DISPONIBILIDAD': return 'background-color: #f0fdf4; border: 1px dashed #22c55e'
                if v == 'T3': return 'background-color: #1e293b; color: white'
                if v == 'T1': return 'background-color: #dcfce7; color: #166534'
                if v == 'T2': return 'background-color: #e0f2fe; color: #0369a1'
                return 'color: #94a3b8'
            st.dataframe(piv[cols].style.map(styler), use_container_width=True)

        with t2:
            st.subheader("Validación de Cobertura")
            cob = df_f[~df_f['Resultado'].str.contains('DESC')].groupby(['Label', 'Resultado'])['Empleado'].count().unstack().fillna(0)
            st.dataframe(cob, use_container_width=True)

        with t3:
            st.subheader("Auditoría de Descansos y Rotación")
            audit = []
            for (g, emp, car), data in df_f.groupby(['Grupo', 'Empleado', 'Cargo']):
                desc = len(data[data['Resultado'].str.contains('DESC')])
                audit.append({"Grupo": g, "Empleado": emp, "Cargo": car, "Descansos Mes": desc, "Semanas": len(semanas_list)})
            st.table(pd.DataFrame(audit))
