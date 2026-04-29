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
    """
    Motor de optimización con filtrado por alcance y PARAMETRIZACIÓN DE HORARIOS.
    """
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
    g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
    
    # 2. Configuración de tiempo con FILTRO DE ALCANCE
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

    if alcance == "1 Semana":
        d_info = [d for d in d_info_completo if d["sem_mes"] == semana_inicio]
    elif alcance == "2 Semanas":
        d_info = [d for d in d_info_completo if d["sem_mes"] >= semana_inicio and d["sem_mes"] < semana_inicio + 2]
    else:
        d_info = d_info_completo

    if not d_info:
        st.error("No hay días para programar en el rango seleccionado.")
        return pd.DataFrame()

    semanas = sorted(list(set([d["sem_iso"] for d in d_info])))

    # 3. Optimizador PuLP
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

    if estado_anterior:
        s_ini = semanas[0]
        for g_n, ult_t in estado_anterior.items():
            if g_n in g_rotan:
                if "T3" in str(ult_t): prob += asig[g_n][s_ini]["T1"] == 0
                elif "T2" in str(ult_t): prob += asig[g_n][s_ini]["T3"] == 1

    prob.solve(PULP_CBC_CMD(msg=0))
    
    # 4. Reconstrucción de matriz
    res_sem = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}
    final_rows = []
    
    turno_vivo = {g: res_sem.get((g, semanas[0]), "T1") for g in g_rotan}
    g_disp = [g for g in n_map.values() if t_map[g] == "DISP"][0]
    u_t_disp = "T1"

    for d_i in d_info:
        descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
        hoy_labels = {}
        for g in g_rotan:
            if d_i["nom"] == d_map[g]:
                hoy_labels[g] = "DESC. LEY"
                turno_vivo[g] = res_sem.get((g, d_i["sem_iso"]), turno_vivo[g])
            else:
                hoy_labels[g] = turno_vivo[g]
        
        if d_i["nom"] == d_map[g_disp]: l_disp = "DESC. LEY"
        else:
            if descansan_hoy:
                t_nec = turno_vivo[descansan_hoy[0]]
                if u_t_disp == "T3": l_disp = "APOYO (Post-Noche)"
                elif u_t_disp == "T2" and t_nec == "T1": l_disp = "T2 (Apoyo)"
                else: l_disp = t_nec
            else:
                l_disp = "T1" if u_t_disp != "T2" else "T2"
        
        if "DESC" not in l_disp and "APOYO" not in l_disp: u_t_disp = l_disp[:2]

        for g_id, g_name in n_map.items():
            val = l_disp if g_name == g_disp else hoy_labels.get(g_name, "T1")
            
            # DETERMINAR HORARIO DINÁMICO
            # Si el turno está en nuestro diccionario de horarios, lo extraemos
            horario_str = ""
            if val in horarios_dict:
                h = horarios_dict[val]
                horario_str = f"{h['inicio']} - {h['fin']}"
            
            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({
                    "Grupo": g_name, 
                    "Empleado": m['nombre'], 
                    "Cargo": m['cargo'], 
                    "Horario": horario_str, # <--- Nueva columna parametrizada
                    "Label": d_i["label"], 
                    "Final": val, 
                    "n_dia": d_i["n"]
                })
                
    return pd.DataFrame(final_rows)

def generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num):
    # Se mantiene la estructura para auxiliares si decides implementarlo luego
    return pd.DataFrame()

def reconstruir_malla_desde_json(json_str):
    try:
        if pd.isna(json_str) or str(json_str).strip() == "": return None
        return pd.read_json(io.StringIO(str(json_str)), orient='split')
    except:
        try: return pd.read_json(io.StringIO(str(json_str)))
        except: return None
