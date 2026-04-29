import pandas as pd
from pulp import *
import calendar
from datetime import datetime
import streamlit as st
import io

@st.cache_data
def load_base():
    """Carga la base de datos de empleados desde el Excel local."""
    try:
        df = pd.read_excel("empleados.xlsx")
        df.columns = df.columns.str.strip().str.lower()
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        df['cargo'] = df['cargo'].astype(str).str.strip()
        df['nombre'] = df['nombre'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error al cargar empleados.xlsx: {e}")
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, horarios_dict, alcance="Mes Completo", semana_inicio=1, estado_anterior=None):
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Distribución de personal
    mas_p = df_raw[df_raw['cargo'].str.contains('Master', case=False)].copy()
    tca_p = df_raw[df_raw['cargo'].str.contains('Tecnico A', case=False)].copy()
    tcb_p = df_raw[df_raw['cargo'].str.contains('Tecnico B', case=False)].copy()
    
    c_list = []
    for g_id, g_name in n_map.items():
        for _ in range(m_req):
            if not mas_p.empty: 
                c_list.append({**mas_p.iloc[0].to_dict(), "grupo": g_name})
                mas_p = mas_p.iloc[1:]
        for _ in range(ta_req):
            if not tca_p.empty: 
                c_list.append({**tca_p.iloc[0].to_dict(), "grupo": g_name})
                tca_p = tca_p.iloc[1:]
        for _ in range(tb_req):
            if not tcb_p.empty: 
                c_list.append({**tcb_p.iloc[0].to_dict(), "grupo": g_name})
                tcb_p = tcb_p.iloc[1:]
    
    df_celulas = pd.DataFrame(c_list)
    g_rotan = [g for g in n_map.values() if t_map.get(g) == "ROTA"]
    
    # 2. Configuración de tiempo
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    d_info_completo = []
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        sem_del_mes = (d - 1) // 7 + 1
        d_info_completo.append({
            "n": d, 
            "nom": DIAS_SEMANA[fecha.weekday()], 
            "sem_iso": fecha.isocalendar()[1], 
            "sem_mes": sem_del_mes,
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })

    d_info = d_info_completo # Simplificado para volver a la base estable
    semanas = sorted(list(set([d["sem_iso"] for d in d_info])))

    # 3. Optimizador PuLP (Lógica original de rotación semanal)
    prob = LpProblem("MovilGo_Modular", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    
    for s in semanas:
        for t in LISTA_TURNOS:
            prob += lpSum([asig[g][s][t] for g in g_rotan]) == 1
        for g in g_rotan:
            prob += lpSum([asig[g][s][t] for t in LISTA_TURNOS]) == 1
    
    for g in g_rotan:
        for i in range(len(semanas)-1):
            s1, s2 = semanas[i], semanas[i+1]
            prob += asig[g][s1]["T1"] <= asig[g][s2]["T2"]
            prob += asig[g][s1]["T2"] <= asig[g][s2]["T3"]
            prob += asig[g][s1]["T3"] <= asig[g][s2]["T1"]

    prob.solve(PULP_CBC_CMD(msg=0))
    
    # 4. Reconstrucción de matriz
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}
    final_rows = []
    
    # Identificar grupo de disponibilidad (DISP)
    g_disp_list = [g for g in n_map.values() if t_map.get(g) == "DISP"]
    g_disp = g_disp_list[0] if g_disp_list else None
    u_t_disp = "T1"

    for d_i in d_info:
        hoy_labels = {}
        descansan_hoy = [g for g in g_rotan if d_map.get(g) == d_i["nom"]]
        
        for g in g_rotan:
            t_de_la_semana = res_sem.get((g, d_i["sem_iso"]), "T1")
            if d_i["nom"] == d_map.get(g):
                hoy_labels[g] = "DESC. LEY"
            else:
                hoy_labels[g] = t_de_la_semana
        
        # Lógica para el grupo DISP
        l_disp = "T1"
        if g_disp:
            if d_i["nom"] == d_map.get(g_disp):
                l_disp = "DESC. LEY"
            elif descansan_hoy:
                l_disp = res_sem.get((descansan_hoy[0], d_i["sem_iso"]), "T1")
            else:
                l_disp = "T1"

        # Armar filas finales
        for g_id, g_name in n_map.items():
            val = l_disp if g_name == g_disp else hoy_labels.get(g_name, "T1")
            
            # Obtener horario del diccionario parametrizado
            h_str = ""
            # Buscamos el turno (T1, T2 o T3) dentro del valor, incluso si dice "T1 (Apoyo)"
            turno_key = next((tk for tk in LISTA_TURNOS if tk in val), None)
            if turno_key and turno_key in horarios_dict:
                h = horarios_dict[turno_key]
                h_str = f"{h['inicio']} - {h['fin']}"
            
            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({
                    "Grupo": g_name, 
                    "Empleado": m['nombre'], 
                    "Cargo": m['cargo'], 
                    "Horario": h_str,
                    "Dia": d_i["label"], 
                    "Turno": val, 
                    "n_dia": d_i["n"]
                })
                
    return pd.DataFrame(final_rows)
