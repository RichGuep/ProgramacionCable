import streamlit as st
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro", layout="wide", page_icon="⚡")

# --- 2. LOGIN ---
def login():
    if 'auth' not in st.session_state:
        st.session_state['auth'] = False

    if not st.session_state['auth']:
        st.title("🔐 MovilGo Login")
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")

        if st.button("Ingresar"):
            if user == "richard.guevara@greenmovil.com.co" and pwd == "Admin2026":
                st.session_state['auth'] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        st.stop()

login()

# --- 3. CARGA DATOS ---
@st.cache_data
def load_data():
    df = pd.read_excel("empleados.xlsx")
    df.columns = df.columns.str.strip().str.lower()
    return df

df_raw = load_data()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")

    meses = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]

    mes_sel = st.selectbox("Mes", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_sel) + 1

    cargo_sel = st.selectbox("Cargo", sorted(df_raw['cargo'].unique()))

# --- CUPOS POR CARGO ---
cupos_por_cargo = {
    "Master": 2,
    "Tecnico A": 7,
    "Tecnico B": 3
}

cupo_fijo = cupos_por_cargo.get(cargo_sel, 2)

# --- 5. CALENDARIO ---
num_dias = calendar.monthrange(2026, mes_num)[1]
cal = calendar.Calendar(firstweekday=0)
semanas = [[d for d in sem if d != 0] for sem in cal.monthdayscalendar(2026, mes_num)]

dias = list(range(1, num_dias + 1))
turnos = ["AM", "PM", "Noche"]

# --- 6. MOTOR ---
if st.button("🚀 GENERAR MALLA"):

    df_f = df_raw[df_raw['cargo'] == cargo_sel].copy()
    empleados = df_f['nombre'].tolist()

    # --- GRUPOS A/B ---
    grupo_A = empleados[::2]
    grupo_B = empleados[1::2]

    prob = LpProblem("Turnos", LpMaximize)

    # Variables
    asig = LpVariable.dicts("Asig", (empleados, dias, turnos), cat='Binary')
    descanso = LpVariable.dicts("Descanso", (empleados, dias), cat='Binary')

    # --- OBJETIVO ---
    prob += lpSum(asig[e][d][t] for e in empleados for d in dias for t in turnos)

    # --- RESTRICCIONES GENERALES ---
    for e in empleados:

        for d in dias:
            # Solo una actividad por día
            prob += lpSum(asig[e][d][t] for t in turnos) + descanso[e][d] == 1

            if d < num_dias:
                # No noche → siguiente día
                prob += asig[e][d]["Noche"] + lpSum(asig[e][d+1][t] for t in turnos) <= 1

                # No PM → AM
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1

    # --- IDENTIFICAR SABADOS Y DOMINGOS ---
    sabados = [d for d in dias if datetime(2026, mes_num, d).weekday() == 5]
    domingos = [d for d in dias if datetime(2026, mes_num, d).weekday() == 6]

    # --- ROTACIÓN POR GRUPOS (CLAVE) ---
    for i, semana in enumerate(semanas):

        sab = [d for d in semana if d in sabados]
        dom = [d for d in semana if d in domingos]

        if not sab and not dom:
            continue

        grupo_descansa = grupo_A if i % 2 == 0 else grupo_B

        for e in empleados:
            if e in grupo_descansa:
                for d in sab + dom:
                    prob += descanso[e][d] == 1
            else:
                for d in sab + dom:
                    prob += descanso[e][d] == 0

    # --- COMPENSATORIOS FLEXIBLES ---
    for i, semana in enumerate(semanas[:-1]):

        dias_sig = [
            d for d in semanas[i+1]
            if datetime(2026, mes_num, d).weekday() < 5
        ]

        for e in empleados:
            if dias_sig:
                # máximo 2 compensatorios (flexible)
                prob += lpSum(descanso[e][d] for d in dias_sig) <= 2

    # --- COBERTURA POR TURNO (FLEXIBLE) ---
    for d in dias:
        for t in turnos:
            prob += lpSum(asig[e][d][t] for e in empleados) >= cupo_fijo

    # --- SOLVER ---
    prob.solve(PULP_CBC_CMD(msg=0, timeLimit=60))

    if LpStatus[prob.status] not in ['Optimal', 'Not Solved']:
        st.error("❌ No se pudo generar solución (modelo muy restringido)")
    else:
        res = []

        for d in dias:
            dn = ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(2026, mes_num, d).weekday()]

            for e in empleados:
                turno = "---"
                for t in turnos:
                    if value(asig[e][d][t]) == 1:
                        turno = t

                res.append({
                    "Dia": d,
                    "Label": f"{d}-{dn}",
                    "Empleado": e,
                    "Turno": turno
                })

        df_res = pd.DataFrame(res)

        # --- CLASIFICACIÓN ---
        df_res['Final'] = ""

        for d in dias:
            for t in turnos:
                idxs = df_res[(df_res['Dia'] == d) & (df_res['Turno'] == t)].index

                for i, idx in enumerate(idxs):
                    df_res.at[idx, 'Final'] = f"TITULAR {t}" if i < cupo_fijo else f"DISPONIBLE {t}"

        for idx in df_res[df_res['Turno'] == "---"].index:
            df_res.at[idx, 'Final'] = "DESCANSO"

        st.session_state['df_final'] = df_res

# --- 7. VISUALIZACIÓN ---
if 'df_final' in st.session_state:

    df_v = st.session_state['df_final']

    st.subheader("📅 Malla Maestra")

    m = df_v.pivot(index='Empleado', columns='Label', values='Final')
    cols = sorted(m.columns, key=lambda x: int(x.split('-')[0]))

    def color(v):
        if "TITULAR" in v: return 'background-color:#cce5ff'
        if "DISPONIBLE" in v: return 'background-color:#d4edda'
        if "DESCANSO" in v: return 'background-color:#ffd966'
        return ''

    st.dataframe(m[cols].style.map(color), use_container_width=True)

    st.subheader("📊 Cobertura")
    cob = df_v[df_v['Final'].str.contains("TITULAR")].groupby("Label").size()
    st.bar_chart(cob)
