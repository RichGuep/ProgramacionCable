import sqlite3
import pandas as pd
import os
import streamlit as st

DB_NAME = "movilgo_data.db"

def load_base():
    """Carga inicial de seguridad si no hay datos."""
    data = [
        {"nombre": "TECNICO MAESTRO 1", "cargo": "MASTER", "grupo": "G1"},
        {"nombre": "TECNICO MAESTRO 2", "cargo": "MASTER", "grupo": "G2"},
        {"nombre": "TECNICO A1", "cargo": "TECNICO A", "grupo": "G1"},
        {"nombre": "TECNICO B1", "cargo": "TECNICO B", "grupo": "G3"}
    ]
    return pd.DataFrame(data)

def read_db(table_name):
    try:
        if not os.path.exists(DB_NAME): return None
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except Exception:
        return None

def save_db(df, table_name):
    try:
        conn = sqlite3.connect(DB_NAME)
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error al guardar en DB: {e}")
        return False
