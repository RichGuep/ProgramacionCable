# ==============================
# BACKEND - FASTAPI + OPTIMIZADOR
# ==============================

from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
from pulp import *
import calendar
from datetime import datetime

app = FastAPI()

TURNOS = ["AM", "PM", "Noche"]

class InputData(BaseModel):
    empleados: list
    demanda: dict
    mes: int
    anio: int

@app.post("/generar_malla")
def generar_malla(data: InputData):

    empleados = data.empleados
    demanda = data.demanda
    mes = data.mes
    anio = data.anio

    num_dias = calendar.monthrange(anio, mes)[1]

    dias_info = [{
        "n": d,
        "nombre": ["Lun","Mar","Mie","Jue","Vie","Sab","Dom"][datetime(anio, mes, d).weekday()]
    } for d in range(1, num_dias+1)]

    prob = LpProblem("Turnos", LpMaximize)

    asig = LpVariable.dicts("A", (range(len(empleados)), range(1, num_dias+1), TURNOS), cat='Binary')

    # OBJETIVO
    prob += lpSum(asig[e][d][t] for e in range(len(empleados)) for d in range(1, num_dias+1) for t in TURNOS)

    # COBERTURA
    for d in range(1, num_dias+1):
        for t in TURNOS:
            prob += lpSum(asig[e][d][t] for e in range(len(empleados))) >= demanda[t]["min"]
            prob += lpSum(asig[e][d][t] for e in range(len(empleados))) <= demanda[t]["max"]

    # RESTRICCIONES
    for e in range(len(empleados)):
        for d in range(1, num_dias+1):
            prob += lpSum(asig[e][d][t] for t in TURNOS) <= 1

            if d < num_dias:
                prob += asig[e][d]["Noche"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["PM"] + asig[e][d+1]["AM"] <= 1
                prob += asig[e][d]["Noche"] + asig[e][d+1]["PM"] <= 1

    prob.solve()

    resultado = []
    for e in range(len(empleados)):
        for d in range(1, num_dias+1):
            turno = "DESCANSO"
            for t in TURNOS:
                if value(asig[e][d][t]) == 1:
                    turno = t
            resultado.append({
                "empleado": empleados[e],
                "dia": d,
                "turno": turno
            })

    return resultado


# ==============================
# FRONTEND - STREAMLIT PRO
# ==============================

import streamlit as st
import requests
import pandas as pd

st.set_page_config(layout="wide")

st.title("⚡ MovilGo Enterprise Scheduler")

st.sidebar.header("Configuración")
mes = st.sidebar.selectbox("Mes", list(range(1,13)))
anio = st.sidebar.number_input("Año", value=2026)

st.sidebar.subheader("Demanda por turno")
demanda = {
    "AM": {"min": st.sidebar.number_input("AM min",1,10,2), "max": st.sidebar.number_input("AM max",1,10,3)},
    "PM": {"min": st.sidebar.number_input("PM min",1,10,2), "max": st.sidebar.number_input("PM max",1,10,3)},
    "Noche": {"min": st.sidebar.number_input("Noche min",1,10,1), "max": st.sidebar.number_input("Noche max",1,10,2)}
}

empleados = st.text_area("Empleados (uno por línea)").split("\n")

if st.button("Generar Malla"):
    payload = {
        "empleados": empleados,
        "demanda": demanda,
        "mes": mes,
        "anio": anio
    }

    res = requests.post("http://localhost:8000/generar_malla", json=payload)
    data = res.json()

    df = pd.DataFrame(data)
    st.dataframe(df)


# ==============================
# INSTRUCCIONES
# ==============================

# 1. Ejecutar backend:
# uvicorn main:app --reload

# 2. Ejecutar frontend:
# streamlit run app.py

# 3. Abrir navegador:
# http://localhost:8501
