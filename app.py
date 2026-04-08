import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

st.set_page_config(page_title="Programador Pro 2026 - Ley 100%", layout="wide")
st.title("🗓️ Programación: Compensatorios Semanales Obligatorios")

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
    st.error(f"Error al leer archivo: {e}"); st.stop()

# --- 2. CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Parámetros")
    ano_sel = st.selectbox("Año", [2025, 2026, 2027], index=1)
    meses_n = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    mes_sel = st.selectbox("Mes", meses_n, index=datetime.now().month - 1)
    mes_num = meses_n.index(mes_sel) + 1
    cargo_sel = st.selectbox("Cargo", sorted(df[col_car].unique()))
    cupo_manual = st.number_input("Cupo por turno", value=2)
    st.divider()
    tipo_vista = st.radio("Visualización:", ["Vista por Semanas", "Mes Completo"])

# --- 3. CALENDARIO ---
num_dias = calendar.monthrange(ano_sel, mes_num)[1]
dias_info = []
dias_esp = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
for d in range(1, num_dias + 1):
    fecha = datetime(ano_sel, mes_num, d)
    n_semana = (d + fecha.replace(day=1).weekday() - 1) // 7 + 1
    dias_info.append({"n": d, "nombre": dias_esp[fecha.weekday()], "semana": n_semana, "label": f"{d} - {dias_esp[fecha.weekday()]}"})

# --- 4. MOTOR DE OPTIMIZACIÓN ---
if st.button(f"🚀 Generar Malla con Compensatorios"):
    df_f = df[df[col_car] == cargo_sel].copy()
    turnos = ["AM", "PM", "Noche"]
    prob = LpProblem("Malla_Legal_Final", LpMaximize)
    asig = LpVariable.dicts("Asig", (df_f[col_nom], range(1, num_dias + 1), turnos), cat='Binary')
    
    # Objetivo: Cobertura máxima
    prob += lpSum([asig[e][d][t] for e in df_f[col_nom] for d in range(1, num_dias + 1) for t in turnos])

    for d_i in dias_info:
        for t in turnos:
            prob += lpSum([asig[e][d_i["n"]][t] for e in df_f[col_nom]]) <= cupo_manual

    for _, row in df_f.iterrows():
        e = row[col_nom]
        dia_c_nom = "Sab" if "sabado" in row[col_des] else "Dom"
        for d in range(1, num_dias + 1):
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
            if d < num_dias: # Higiene sueño
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
        
        # 2 Descansos de fin de semana contractuales obligatorios
        f_c = [di["n"] for di in dias_info if di["nombre"] == dia_c_nom]
        prob += lpSum([asig[e][d][t] for d in f_c for t in turnos]) == (len(f_c) - 2)
        
        # Bajamos la exigencia de días laborados a 18 para asegurar que existan huecos para compensar
        prob += lpSum([asig[e][d][t] for d in range(1, num_dias + 1) for t in turnos]) >= 18

    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        res_list = []
        for d_i in dias_info:
            for e in df_f[col_nom]:
                t_asig = "---"
                for t in turnos:
                    if value(asig[e][d_i["n"]][t]) == 1: t_asig = t
                res_list.append({"Dia": d_i["n"], "Label": d_i["label"], "Semana": d_i["semana"], "Nom_Dia": d_i["nombre"], "Empleado": e, "Turno": t_asig, "Contrato": df_f[df_f[col_nom]==e][col_des].values[0]})
        
        df_res = pd.DataFrame(res_list)
        lista_final = []
        for emp, grupo in df_res.groupby("Empleado"):
            grupo = grupo.sort_values("Dia").copy()
            dia_c_nom = "Sab" if "sabado" in grupo['Contrato'].iloc[0] else "Dom"
            
            # 1. Marcar los 2 Contractuales de Finde
            idx_f = grupo[(grupo['Turno'] == '---') & (grupo['Nom_Dia'] == dia_c_nom)].head(2).index
            grupo.loc[idx_f, 'Turno'] = 'DESC. CONTRATO'
            
            # 2. Lógica de Compensación: Por cada finde TRABAJADO, buscar el primer hueco L-V siguiente
            f_trabajados = grupo[(grupo['Nom_Dia'] == dia_c_nom) & (grupo['Turno'].isin(turnos))]
            for _, row_ft in f_trabajados.iterrows():
                # Buscamos un compensatorio en los 7 días posteriores
                dia_inicio_busqueda = row_ft['Dia']
                idx_comp = grupo[(grupo['Dia'] > dia_inicio_busqueda) & 
                                 (grupo['Dia'] <= dia_inicio_busqueda + 7) & 
                                 (grupo['Turno'] == '---') & 
                                 (~grupo['Nom_Dia'].isin(['Sab', 'Dom']))].head(1).index
                if not idx_comp.empty:
                    grupo.loc[idx_comp, 'Turno'] = 'DESC. L-V'

            # 3. Todo lo que sobre es DISPO
            grupo.loc[grupo['Turno'] == '---', 'Turno'] = 'DISPO'
            lista_final.append(grupo)
        
        st.session_state['df_final'] = pd.concat(lista_final).reset_index(drop=True)
        st.success("✅ Malla generada con compensatorios estrictos.")
    else:
        st.error("❌ Conflicto de reglas. Intente bajar el cupo operativo.")

# --- 5. VISUALIZACIÓN ---
if 'df_final' in st.session_state:
    df_view = st.session_state['df_final']
    df_view['ID_Full'] = df_view['Empleado'] + " (" + df_view['Contrato'].str.upper() + ")"

    def color_fn(val):
        styles = {
            'DESC. CONTRATO': 'background-color: #ffb3b3; color: #b30000; font-weight: bold',
            'DESC. L-V': 'background-color: #ffd9b3; color: #804000; font-weight: bold',
            'DISPO': 'background-color: #e6f3ff; color: #004080'
        }
        return styles.get(val, '')

    t_malla, t_filtro, t_ley = st.tabs(["📅 Malla General", "🔍 Filtro Empleado", "⚖️ Auditoría"])

    with t_malla:
        if tipo_vista == "Mes Completo":
            m_f = df_view.pivot(index='ID_Full', columns='Label', values='Turno')
            st.dataframe(m_f[sorted(m_f.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(color_fn), use_container_width=True)
        else:
            for s in sorted(df_view['Semana'].unique()):
                st.write(f"### Semana {s}")
                m_s = df_view[df_view['Semana'] == s].pivot(index='ID_Full', columns='Label', values='Turno')
                st.dataframe(m_s[sorted(m_s.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(color_fn), use_container_width=True)

    with t_filtro:
        sel = st.multiselect("Consultar Empleado:", sorted(df_view['Empleado'].unique()))
        if sel:
            m_i = df_view[df_view['Empleado'].isin(sel)].pivot(index='ID_Full', columns='Label', values='Turno')
            st.dataframe(m_i[sorted(m_i.columns, key=lambda x: int(x.split(' - ')[0]))].style.map(color_fn), use_container_width=True)

    with t_ley:
        audit = []
        for e, g in df_view.groupby("Empleado"):
            dia_c = "Sab" if "sabado" in g['Contrato'].iloc[0] else "Dom"
            f_trab = len(g[(g['Nom_Dia'] == dia_c) & (g['Turno'].isin(["AM","PM","Noche"]))])
            audit.append({
                "Empleado": e, 
                "Finde Contrato Trabajado": f_trab,
                "Compensatorios Otorgados": len(g[g['Turno'] == 'DESC. L-V']),
                "Estado Legal": "✅ CUMPLIDO" if len(g[g['Turno'] == 'DESC. L-V']) >= f_trab else "⚠️ REVISAR"
            })
        st.table(pd.DataFrame(audit))
