import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026 - Filtros Avanzados", layout="wide")
st.title("🗓️ Programación con Filtro Individual y Cumplimiento Legal")

# --- 1. CARGA DE DATOS ---
try:
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    col_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), None)
    col_car = next((c for c in df.columns if 'car' in c), None)
    col_des = next((c for c in df.columns if 'des' in c), None)
    df[col_nom] = df[col_nom].astype(str).str.strip()
    df[col_car] = df[col_car].astype(str).str.strip()
    df[col_des] = df[col_des].astype(str).str.strip().str.lower()
except Exception as e:
    st.error(f"Error: {e}"); st.stop()

# --- 2. CONFIGURACIÓN LATERAL ---
with st.sidebar:
    st.header("⚙️ Parámetros Generales")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)
    st.divider()
    tipo_vista = st.radio("Visualización Principal:", ["Vista por Semanas", "Mes Completo"])

# --- 3. CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_info = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_info.append({
        "n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana,
        "label": f"{d} - {dias_esp[fecha.weekday()]}"
    })

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla y Habilitar Filtros"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Cumplimiento_Legal_Filtros", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')
    
    # Objetivo: Maximizar cobertura y estabilidad
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    for d_i in dias_info:
        d = d_i["n"]
        for t in turnos:
            prob += lpSum([asig[e][d][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e = row[col_nom]
        dia_c_nom = "Sab" if "sabado" in row[col_des] else "Dom"
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
        
        # Reglas legales
        f_contractuales = [di["n"] for di in dias_info if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in f_contractuales for t in turnos]) == (len(f_contractuales) - 2)
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 19

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        # Procesamiento de Malla
        res_list = []
        for d_i in dias_info:
            d = d_i["n"]
            for e in df_f[col_nom]:
                t_asig = "---"
                for t in turnos:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res_list.append({
                    "Dia": d, "Label": d_i["label"], "Semana": d_i["semana"], 
                    "Nom_Dia": d_i["nombre"], "Empleado": e, "Turno": t_asig,
                    "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]
                })
        
        df_res = pd.DataFrame(res_list)
        
        # Aplicación de Descansos Compensatorios Semanales
        lista_final = []
        for emp, grupo in df_res.groupby("Empleado"):
            grupo = grupo.sort_values("Dia").copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
            
            f_trabajados = grupo[(grupo['Nom_Dia'] == dia_c_nom) & (grupo['Turno'].isin(turnos))]
            for _, row_f in f_trabajados.iterrows():
                idx_comp = grupo[(grupo['Dia'] > row_f['Dia']) & (grupo['Dia'] <= row_f['Dia'] + 7) & 
                                 (grupo['Turno'] == '---') & (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].index
                if not idx_comp.empty:
                    grupo.loc[idx_comp[0], 'Turno'] = 'DESC. L-V'
            
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)

        df_final = pd.concat(lista_final).reset_index(drop=True)
        df_final['ID_Full'] = df_final['Empleado'] + " (" + df_final['Contrato'].str.upper() + ")"

        # Estilo visual
        def style_fn(val):
            styles = {
                'DESC. CONTRATO': 'background-color: #ffb3b3; color: #b30000; font-weight: bold',
                'DESC. L-V': 'background-color: #ffd9b3; color: #804000; font-weight: bold',
                'DISPO': 'background-color: #e6f3ff; color: #004080'
            }
            return styles.get(val, '')

        # --- SECCIÓN DE TABS ---
        tab_main, tab_filter, tab_audit = st.tabs(["📊 Malla General", "🔍 Consulta por Empleado", "⚖️ Auditoría Legal"])

        with tab_main:
            if tipo_vista == "Mes Completo":
                m_full = df_final.pivot(index='ID_Full', columns='Label', values='Turno')
                cols_sorted = sorted(m_full.columns, key=lambda x: int(x.split(' - ')[0]))
                st.dataframe(m_full[cols_sorted].style.map(style_fn), use_container_width=True)
            else:
                sems = sorted(df_final['Semana'].unique())
                for s in sems:
                    st.subheader(f"Semana {s}")
                    m_s = df_final[df_final['Semana'] == s].pivot(index='ID_Full', columns='Label', values='Turno')
                    cols_s = sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))
                    st.dataframe(m_s[cols_s].style.map(style_fn), use_container_width=True)

        with tab_filter:
            st.subheader("Buscador de Programación Individual")
            emp_busqueda = st.multiselect("Seleccione el o los empleados a consultar:", sorted(df_final['Empleado'].unique()))
            
            if emp_busqueda:
                df_busqueda = df_final[df_final['Empleado'].isin(emp_busqueda)]
                m_busqueda = df_busqueda.pivot(index='ID_Full', columns='Label', values='Turno')
                cols_b = sorted(m_busqueda.columns, key=lambda x: int(x.split(' - ')[0]))
                st.write("### Horario Detallado")
                st.dataframe(m_busqueda[cols_b].style.map(style_fn), use_container_width=True)
                
                # Resumen rápido del filtrado
                for e in emp_busqueda:
                    g_e = df_final[df_final['Empleado'] == e]
                    st.info(f"**{e}**: Trabajará {len(g_e[g_e['Turno'].isin(turnos)])} días. "
                            f"Descansos: {len(g_e[g_e['Turno'].str.contains('DESC')])} | DISPO: {len(g_e[g_e['Turno']=='DISPO'])}")
            else:
                st.info("Seleccione un nombre arriba para ver su detalle.")

        with tab_audit:
            st.subheader("Validación de Cumplimiento")
            audit_list = []
            for e, g in df_final.groupby("Empleado"):
                f_trab = len(g[(g['Nom_Dia'] == ("Sab" if "sabado" in g['Contrato'].iloc[0] else "Dom")) & (g['Turno'].isin(turnos))])
                audit_list.append({
                    "Empleado": e, "Findes Trabajados": f_trab,
                    "Compensatorios L-V": len(g[g['Turno'] == 'DESC. L-V']),
                    "Ley 1-1": "✅ Cumple" if len(g[g['Turno'] == 'DESC. L-V']) >= f_trab else "❌ Pendiente",
                    "Días DISPO": len(g[g['Turno'] == 'DISPO'])
                })
            st.table(pd.DataFrame(audit_list))

    else:
        st.error("❌ Conflicto de reglas. Intenta reducir el cupo o revisar el personal.")
