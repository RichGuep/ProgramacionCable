import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro - Seguridad T3 y Refuerzos", layout="wide", page_icon="🛡️")
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
        m_req = st.number_input("Masters por Célula", 1, 5, 2)
        ta_req = st.number_input("Técnicos A por Célula", 1, 15, 7)
        tb_req = st.number_input("Técnicos B por Célula", 1, 10, 3)
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

    st.title(f"📊 Control Operativo: {mes_sel} {ano_sel}")
    
    with st.expander("🏷️ Nombres y Descansos de Grupos", expanded=True):
        nombres_map, descansos_map = {}, {}
        cols = st.columns(num_g if num_g > 0 else 1)
        for i in range(num_g):
            with cols[i]:
                n_s = st.text_input(f"Nombre G{i+1}", f"GRUPO {i+1}", key=f"n_{i}")
                d_s = st.selectbox(f"Día Ley {n_s}", ["Lunes", "Viernes", "Sabado", "Domingo"], index=i % 4, key=f"d_{i}")
                nombres_map[f"G{i+1}"] = n_s
                descansos_map[n_s] = d_s

    def armar_celulas(df, m, ta, tb, n_map):
        mas = df[df['cargo'].str.contains('Master', case=False, na=False)].copy()
        tca = df[df['cargo'].str.contains('Tecnico A', case=False, na=False)].copy()
        tcb = df[df['cargo'].str.contains('Tecnico B', case=False, na=False)].copy()
        final = []
        for i in range(len(n_map)):
            g_name = n_map[f"G{i+1}"]
            for _ in range(m): final.append({**mas.iloc[0].to_dict(), "grupo": g_name}); mas = mas.iloc[1:]
            for _ in range(ta): final.append({**tca.iloc[0].to_dict(), "grupo": g_name}); tca = tca.iloc[1:]
            for _ in range(tb): final.append({**tcb.iloc[0].to_dict(), "grupo": g_name}); tcb = tcb.iloc[1:]
        return pd.DataFrame(final)

    df_celulas = armar_celulas(df_raw, m_req, ta_req, tb_req, nombres_map)
    g_finales = list(nombres_map.values())

    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_range = range(1, num_dias + 1)
    dias_es = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    d_info = [{"n": d, "nom": dias_es[datetime(ano_sel, mes_num, d).weekday()], "sem": datetime(ano_sel, mes_num, d).isocalendar()[1], "lab": f"{d}-{dias_es[datetime(ano_sel, mes_num, d).weekday()]}"} for d in d_range]
    semanas_list = sorted(list(set([d["sem"] for d in d_info])))

    if st.button("⚡ GENERAR MALLA (BLOQUEO T3 ACTIVO)"):
        with st.status("Validando seguridad de descansos post-T3...", expanded=True) as status:
            prob = LpProblem("MovilGo_Security", LpMaximize)
            asig_sem = LpVariable.dicts("AsigSem", (g_finales, semanas_list, LISTA_TURNOS), cat='Binary')
            
            prob += lpSum([asig_sem[g][s][t] for g in g_finales for s in semanas_list for t in LISTA_TURNOS])

            for s in semanas_list:
                for t in LISTA_TURNOS:
                    # Garantizar cobertura base
                    prob += lpSum([asig_sem[g][s][t] for g in g_finales]) >= 1
                for g in g_finales:
                    prob += lpSum([asig_sem[g][s][t] for t in LISTA_TURNOS]) <= 1

            # REGLA DE ORO: T3 NO PUEDE PASAR A T1/T2 SIN DESCANSO (Rotación Segura)
            for g in g_finales:
                for i in range(len(semanas_list)-1):
                    s1, s2 = semanas_list[i], semanas_list[i+1]
                    # Solo puede rotar T3 -> Descanso -> T2 (La lógica de días de ley se encarga del descanso)
                    # Forzamos que después de T3 solo se pueda ir a T2 (PM) para dar margen de sueño
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
                        final_data.append({
                            "Dia": d_i["n"], "Label": d_i["lab"], "Nom_Dia": d_i["nom"], "Semana": d_i["sem"], 
                            "Empleado": m['nombre'], "Cargo": m['cargo'], "Grupo": g, "Turno": t_f, "Ley": es_l
                        })

            df_res = pd.DataFrame(final_data)
            p_rows = []
            for _, g_emp in df_res.groupby("Empleado"):
                g_emp = g_emp.sort_values("Dia").copy()
                for s in semanas_list:
                    f_s = g_emp[g_emp['Semana'] == s]
                    t_s = f_s['Turno'].iloc[0]
                    g_emp.loc[f_s.index, 'Resultado'] = t_s
                    idx_l = f_s[f_s['Ley']].index
                    if not idx_l.empty: g_emp.loc[idx_l, 'Resultado'] = "DESC. LEY"
                p_rows.append(g_emp)

            st.session_state['malla_final'] = pd.concat(p_rows)
            status.update(label="✅ Malla generada con cargos y seguridad T3.", state="complete")

    if 'malla_final' in st.session_state:
        df_v = st.session_state['malla_final']
        
        tab_m, tab_a = st.tabs(["📅 Malla Operativa (Con Cargos)", "⚖️ Auditoría de Descansos"])
        
        with tab_m:
            # Creamos el pivote usando Grupo, Empleado y Cargo como índices
            piv = df_v.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Resultado')
            cols = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))
            
            def styler(v):
                if 'LEY' in str(v): return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'
                if 'DISPO' in str(v) and v != 'DISPONIBILIDAD': return 'background-color: #fef9c3; color: #854d0e; border: 1px dashed #ca8a04'
                if v == 'T3': return 'background-color: #1e293b; color: white'
                if v == 'T1': return 'background-color: #dcfce7; color: #166534'
                if v == 'T2': return 'background-color: #e0f2fe; color: #0369a1'
                return 'color: #94a3b8'
                
            st.dataframe(piv[cols].style.map(styler), use_container_width=True)

        with tab_a:
            st.subheader("Cumplimiento de Descansos por Persona")
            audit = []
            for (g, emp, car), data in df_v.groupby(['Grupo', 'Empleado', 'Cargo']):
                d_ley = len(data[data['Resultado'] == 'DESC. LEY'])
                audit.append({
                    "Grupo": g, "Nombre": emp, "Cargo": car,
                    "Descansos de Ley": d_ley,
                    "Estado": "✅ OK" if d_ley >= len(semanas_list)-1 else "⚠️ REVISAR"
                })
            st.table(pd.DataFrame(audit))
