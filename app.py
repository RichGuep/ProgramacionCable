import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Freeway Final", layout="wide")
TURNOS = ["AM", "PM", "Noche"]

# --- CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        return df.rename(columns={'nombre':'nombre','cargo':'cargo','descanso':'descanso_ley'})
    except: return None

df_raw = load_data()

if df_raw is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
        mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
        mes_num = meses.index(mes_sel) + 1
        cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))
        cupo_fijo = 2 

    num_dias = calendar.monthrange(2026, mes_num)[1]
    dias_rango = range(1, num_dias + 1)
    
    if st.button("🚀 GENERAR PROGRAMACIÓN FREEWAY"):
        df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
        empleados = df_f['nombre'].tolist()
        
        # Modelo de Minimización de Errores (Garantiza que siempre salga una malla)
        prob = LpProblem("Freeway_Final", LpMinimize)

        # Variables
        asig = LpVariable.dicts("Asig", (empleados, dias_rango, TURNOS), cat='Binary')
        hueco = LpVariable.dicts("Hueco", (dias_rango, TURNOS), lowBound=0, cat='Integer')

        # OBJETIVO: Minimizar huecos en el cupo de 2 personas
        prob += lpSum(hueco[d][t] * 1000 for d in dias_rango for t in TURNOS)

        for d in dias_rango:
            for t in TURNOS:
                # Cupo de 2 personas: Empleados + Hueco >= 2
                prob += lpSum(asig[e][d][t] for e in empleados) + hueco[d][t] >= cupo_fijo

        for _, row in df_f.iterrows():
            e = row['nombre']
            dia_ley = "Sab" if "sab" in str(row['descanso_ley']).lower() else "Dom"
            fds_dias = [d for d in dias_rango if ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()] == dia_ley]
            
            # Máximo 1 turno por día
            for d in dias_rango:
                prob += lpSum(asig[e][d][t] for t in TURNOS) <= 1
                if d < num_dias:
                    prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in TURNOS) <= 1
                    prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

            # Exactamente 2 descansos de ley en el mes (para que roten 2 sí, 2 no)
            prob += lpSum(asig[e][d][t] for d in fds_dias for t in TURNOS) == (len(fds_dias) - 2)

        prob.solve(PULP_CBC_CMD(msg=0))

        # --- PROCESAMIENTO DE RESULTADOS ---
        res = []
        for d in dias_rango:
            dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]
            for e in empleados:
                t_asig = "---"
                for t in TURNOS:
                    if value(asig[e][d][t]) == 1: t_asig = t
                res.append({"Dia": d, "Label": f"{d}-{dn}", "Nom_Dia": dn, "Empleado": e, "Turno": t_asig, "Ley": df_f[df_f['nombre']==e]['descanso_ley'].values[0]})

        df_res = pd.DataFrame(res)
        df_res['Final'] = ""
        
        # Identificar Titulares y Disponibles
        for (d, t), group in df_res[df_res['Turno'] != "---"].groupby(['Dia', 'Turno']):
            for i, idx in enumerate(group.index):
                df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_fijo else f"DISPONIBLE {t}"
        
        # Identificar Descansos
        for idx in df_res[df_res['Turno'] == "---"].index:
            r = df_res.loc[idx]
            dia_ley_nom = "Sab" if "sab" in str(r['Ley']).lower() else "Dom"
            df_res.at[idx, 'Final'] = "DESC. LEY" if r['Nom_Dia'] == dia_ley_nom else "DESC. COMP."

        # --- MOSTRAR TABLA ---
        st.success("✅ Malla generada con éxito")
        m_f = df_res.pivot(index="Empleado", columns="Label", values="Final")
        cols = sorted(m_f.columns, key=lambda x: int(x.split('-')[0]))
        
        def color_f(v):
            if 'TITULAR' in v: return 'background-color: #003366; color: white; font-weight: bold'
            if 'DISPONIBLE' in v: return 'background-color: #d4edda; color: #155724'
            if 'LEY' in v: return 'background-color: #ff9900; color: white'
            if 'COMP' in v: return 'background-color: #ffd966'
            return ''
            
        st.dataframe(m_f[cols].style.applymap(color_f), use_container_width=True)
