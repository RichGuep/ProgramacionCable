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
        # Buscamos columnas de nombre y cargo con nombres flexibles
        c_nom = next((c for c in df.columns if 'nom' in c or 'emp' in c), "nombre")
        c_car = next((c for c in df.columns if 'car' in c), "cargo")
        df = df.rename(columns={c_nom: 'nombre', c_car: 'cargo'})
        # Limpieza de strings para evitar errores de matching
        df['cargo'] = df['cargo'].astype(str).str.strip()
        df['nombre'] = df['nombre'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Error al cargar empleados.xlsx: {e}")
        return None

def generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num, estado_anterior=None):
    """
    Motor de optimización PuLP con lógica de empalme mensual.
    estado_anterior: Diccionario { 'NombreGrupo': 'UltimoTurno' } del mes pasado.
    """
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    LISTA_TURNOS = ["T1", "T2", "T3"]
    
    # 1. Distribución de personal por categorías
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
    
    # 2. Configuración de tiempo y semanas
    g_rotan = [g for g in n_map.values() if t_map[g] == "ROTA"]
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    
    d_info = []
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        d_info.append({
            "n": d, 
            "nom": DIAS_SEMANA[fecha.weekday()], 
            "sem": fecha.isocalendar()[1], 
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })
    
    semanas = sorted(list(set([d["sem"] for d in d_info])))

    # 3. Optimizador PuLP
    prob = LpProblem("MovilGo_Empalme", LpMinimize)
    asig = LpVariable.dicts("Asig", (g_rotan, semanas, LISTA_TURNOS), cat='Binary')
    
    # Restricciones base
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

    # --- LÓGICA DE EMPALME (MEMORIA DE CONTINUIDAD) ---
    if estado_anterior:
        s_inicial = semanas[0]
        for g_name, ultimo_t in estado_anterior.items():
            if g_name in g_rotan:
                # Bloqueo: Salida de Noche (T3) -> No puede entrar de Mañana (T1)
                if "T3" in str(ultimo_t):
                    prob += asig[g_name][s_inicial]["T1"] == 0
                # Empuje lógico: Si terminó en T2, debe rotar a T3
                elif "T2" in str(ultimo_t):
                    prob += asig[g_name][s_inicial]["T3"] == 1

    prob.solve(PULP_CBC_CMD(msg=0))
    
    # 4. Construcción de la matriz
    res_semanal = {(g, s): t for g in g_rotan for s in semanas for t in LISTA_TURNOS if value(asig[g][s][t]) == 1}
    final_rows = []
    turno_vivo = {g: res_semanal.get((g, semanas[0]), "T1") for g in g_rotan}
    
    grupos_disp = [g for g in n_map.values() if t_map[g] == "DISP"]
    g_disp = grupos_disp[0] if grupos_disp else None
    ultimo_turno_disp = "T1"

    for d_i in d_info:
        descansan_hoy = [g for g in g_rotan if d_map[g] == d_i["nom"]]
        hoy_labels = {}
        for g in g_rotan:
            if d_i["nom"] == d_map[g]:
                hoy_labels[g] = "DESC. LEY"
                turno_vivo[g] = res_semanal.get((g, d_i["sem"]), turno_vivo[g])
            else:
                hoy_labels[g] = turno_vivo[g]
        
        label_disp = "T1"
        if g_disp:
            if d_i["nom"] == d_map[g_disp]:
                label_disp = "DESC. LEY"
            else:
                if descansan_hoy:
                    g_a_cubrir = descansan_hoy[0]
                    t_necesario = turno_vivo[g_a_cubrir]
                    if ultimo_turno_disp == "T3": label_disp = "APOYO (Post-Noche)"
                    elif ultimo_turno_disp == "T2" and t_necesario == "T1": label_disp = "T2 (Apoyo)"
                    else: label_disp = t_necesario
                else:
                    label_disp = "T1" if ultimo_turno_disp != "T2" else "T2"
            
            if "DESC" not in label_disp and "APOYO" not in label_disp:
                ultimo_turno_disp = label_disp[:2]

        for g_id, g_name in n_map.items():
            val_final = label_disp if g_name == g_disp else hoy_labels.get(g_name, "T1")
            for _, m in df_celulas[df_celulas['grupo'] == g_name].iterrows():
                final_rows.append({
                    "Grupo": g_name, "Empleado": m['nombre'], "Cargo": m['cargo'], 
                    "Label": d_i["label"], "Final": val_final, "n_dia": d_i["n"]
                })
                
    return pd.DataFrame(final_rows)

def generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num):
    """Lógica de rotación circular para personal auxiliar."""
    DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    df_aux = df_raw[df_raw['cargo'].str.contains("Auxiliar", case=False, na=False)].copy().reset_index(drop=True)
    if df_aux.empty: return None

    df_aux['equipo'] = [aux_n_map[i % 5] for i in range(len(df_aux))]
    num_dias = calendar.monthrange(ano_sel, mes_num)[1]
    
    d_info_ax = []
    for d in range(1, num_dias + 1):
        fecha = datetime(ano_sel, mes_num, d)
        d_info_ax.append({
            "nom": DIAS_SEMANA[fecha.weekday()], "sem": fecha.isocalendar()[1], 
            "label": f"{d:02d}-{DIAS_SEMANA[fecha.weekday()][:3]}"
        })
    
    semanas_ax = sorted(list(set([d["sem"] for d in d_info_ax])))
    rows_ax = []
    for s_idx, sem in enumerate(semanas_ax):
        pool = ["T1", "T1", "T2", "T2", "DISPONIBILIDAD"]
        offset = s_idx % 5
        turnos_semana = pool[-offset:] + pool[:-offset]
        for d_i in [d for d in d_info_ax if d["sem"] == sem]:
            for eq_idx in range(5):
                eq_name = aux_n_map[eq_idx]
                final_t = "DESC. LEY" if d_i["nom"] == aux_d_map[eq_name] else turnos_semana[eq_idx]
                for _, emp in df_aux[df_aux['equipo'] == eq_name].iterrows():
                    rows_ax.append({"Equipo": eq_name, "Empleado": emp['nombre'], "Label": d_i["label"], "Turno": final_t})
    
    return pd.DataFrame(rows_ax)

def reconstruir_malla_desde_json(json_str):
    """Recupera la malla asegurando que el formato sea válido."""
    try:
        if pd.isna(json_str) or str(json_str).strip() == "":
            return None
        
        # Limpieza de posibles caracteres de escape de Excel
        json_limpio = str(json_str).strip().replace("''", "'")
        
        # Si el JSON parece cortado (no termina en ]), intentamos cerrarlo
        if not json_limpio.endswith(']'):
             # Esto es una medida de emergencia, lo ideal es que no se corte al guardar
             pass 

        return pd.read_json(io.StringIO(json_limpio), orient='records')
    except Exception as e:
        print(f"Error técnico en JSON: {e}")
        return None
