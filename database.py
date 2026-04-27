import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from git import Repo
# --- ESTA ES LA LÍNEA QUE FALTA ---
from logic import load_base 
# ----------------------------------

# Configuración
DB_NAME = "movilgo_data.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

# ... (resto del código de commit_to_github)

def read_db(table_name):
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception as e:
        if "no such table" in str(e).lower():
            if table_name == "empleados":
                # Ahora sí reconocerá load_base porque la importamos arriba
                df_inicial = load_base() 
                save_db(df_inicial, "empleados")
                return df_inicial
            elif table_name == "usuarios":
                df_admin = pd.DataFrame([{"Nombre": "Richard", "Correo": "richard.guevara@greenmovil.com.co", "Rol": "Admin", "Password": "Admin2026"}])
                save_db(df_admin, "usuarios")
                return df_admin
        return None

def save_db(df, table_name):
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        # Intentar persistir en GitHub después de guardar
        # commit_to_github() # Descomenta esto cuando tengas los Secrets listos
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
