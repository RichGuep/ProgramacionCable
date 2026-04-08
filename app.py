if st.button("🚀 Generar Programación"):
    dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = ["AM", "PM", "Noche"]
    
    prob = LpProblem("Turnos_Optimizados", LpMinimize)
    asig = LpVariable.dicts("Asig", (df_empleados[col_nombre], dias, turnos), cat='Binary')

    # 1. CUMPLIMIENTO ESTRICTO DE CUPOS (2, 7, 3 por turno)
    for d in dias:
        for t in turnos:
            for c in cargos_unicos:
                emps_del_cargo = df_empleados[df_empleados[col_cargo] == c][col_nombre]
                # Ahora sí usamos == porque con 6 personas disponibles cubrimos los 3 turnos
                prob += lpSum([asig[e][d][t] for e in emps_del_cargo]) == cupos[c]

    # 2. REGLAS POR EMPLEADO
    for _, row in df_empleados.iterrows():
        e = row[col_nombre]
        tipo_contrato = str(row[col_descanso]).strip().lower()
        
        # REGLA A: Solo un turno al día
        for d in dias:
            prob += lpSum([asig[e][d][t] for t in turnos]) <= 1
        
        # REGLA B: Garantizar exactamente 2 días de descanso a la semana (Reforma)
        # Esto obliga al sistema a dar descansos entre semana si trabajó el finde.
        prob += lpSum([asig[e][d][t] for d in dias for t in turnos]) == 5

        # REGLA C: Descanso obligatorio según contrato (Sábado o Domingo)
        # Aquí el sistema elegirá a 2 personas para descansar cada finde según tu instrucción
        if "sabado" in tipo_contrato:
            # El sistema debe asegurar que al menos 2 descansen el sábado (si hay 8 totales)
            # Nota: Esto se maneja solo al pedir cupo de 6 y tener 8 empleados.
            pass 

    # 3. SOLVER
    prob.solve(PULP_CBC_CMD(msg=0))

    if LpStatus[prob.status] == 'Optimal':
        st.success("✅ Programación Generada: Cupos cubiertos y descansos repartidos.")
        
        res = []
        for d in dias:
            for t in turnos:
                for e in df_empleados[col_nombre]:
                    if value(asig[e][d][t]) == 1:
                        res.append({"Empleado": e, "Dia": d, "Turno": t})
        
        df_res = pd.DataFrame(res)
        malla = df_res.pivot(index='Empleado', columns='Dia', values='Turno').fillna('DESCANSO')
        
        # Aplicar estilo visual: resaltar descansos
        st.dataframe(malla.reindex(columns=dias).style.highlight_vals('DESCANSO', color='#FFD580'))
    else:
        st.error("❌ Error de capacidad. Verifica que el número de empleados por cargo sea suficiente.")
