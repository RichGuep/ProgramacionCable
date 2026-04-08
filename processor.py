import pandas as pd
import requests
from datetime import datetime, timedelta
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
ADMIN_EMAIL = "richard.guevara@greenmovil.com.co"
conn = st.connection("gsheets", type=GSheetsConnection)

def obtener_usuarios():
    try:
        df = conn.read(worksheet="USUARIOS", ttl=0)
        df.columns = [str(c).lower().strip() for c in df.columns]
        # Aseguramos que exista tipo_contrato
        if 'tipo_contrato' not in df.columns: df['tipo_contrato'] = 'Tiempo Completo'
        df['correo'] = df['correo'].astype(str).str.lower().str.strip()
        users_dict = df.set_index('correo').to_dict('index')
        return users_dict
    except:
        return {ADMIN_EMAIL: {"nombre": "Richard Guevara", "tipo_contrato": "Tiempo Completo", "pw": "Admin2026", "rol": "admin"}}

# --- NUEVA FUNCIÓN: CÁLCULO DE DESCANSOS Y COMPENSATORIOS ---
def calcular_metricas_rrhh(df_prg):
    try:
        # 1. Obtener lista de todos los operadores desde USUARIOS
        df_u = conn.read(worksheet="USUARIOS", ttl=0)
        df_u.columns = [str(c).lower().strip() for c in df_u.columns]
        
        # 2. Preparar fechas
        df_prg['fecha_dt'] = pd.to_datetime(df_prg['fecha'])
        df_prg['dia_semana'] = df_prg['fecha_dt'].dt.day_name() # Monday, Tuesday...
        df_prg['semana'] = df_prg['fecha_dt'].dt.isocalendar().week
        
        operadores_activos = df_prg['ope_prog'].unique()
        resumen = []

        for index, user in df_u.iterrows():
            nombre = user['nombre']
            contrato = user.get('tipo_contrato', 'Tiempo Completo')
            
            # Programación del operador
            prog_ope = df_prg[df_prg['ope_prog'] == nombre]
            
            # Sábados y Domingos trabajados
            sabs_trab = prog_ope[prog_ope['dia_semana'] == 'Saturday']['fecha'].nunique()
            doms_trab = prog_ope[prog_ope['dia_semana'] == 'Sunday']['fecha'].nunique()
            
            # Días laborados entre semana (L-V)
            entre_semana = prog_ope[~prog_ope['dia_semana'].isin(['Saturday', 'Sunday'])]
            dias_semana_trab = entre_semana['fecha'].nunique()
            
            # Lógica de compensatorios (Si trabajó Sab y Dom, ¿descansó algún día L-V?)
            # Asumiendo una semana estándar de 5 días hábiles
            semanas_full_work = prog_ope.groupby('semana').filter(lambda x: x['dia_semana'].nunique() >= 6)
            tuvo_compensatorio = "SÍ" if (dias_semana_trab < 5 and (sabs_trab > 0 or doms_trab > 0)) else "NO"

            resumen.append({
                "Operador": nombre,
                "Contrato": contrato,
                "Sábados Trabajados": sabs_trab,
                "Domingos Trabajados": doms_trab,
                "Días L-V": dias_semana_trab,
                "Compensatorio": tuvo_compensatorio
            })
            
        return pd.DataFrame(resumen)
    except:
        return pd.DataFrame()

# ... (Mantener funciones de sincronizar_semana_por_dias y aplicar_gestion_servicio iguales)
