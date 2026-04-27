import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# Conexión optimizada para PlanetScale (MySQL)
engine = create_engine(st.secrets["DB_URL"], pool_pre_ping=True)

def read_sql(table_name):
    """Lee una tabla completa de PlanetScale."""
    try:
        query = f"SELECT * FROM {table_name}"
        return pd.read_sql(query, engine)
    except Exception as e:
        return None

def save_sql(df, table_name):
    """Guarda o actualiza una tabla en PlanetScale."""
    try:
        # Usamos method='multi' para que sea más rápido en la nube
        df.to_sql(table_name, engine, if_exists='replace', index=False, method='multi')
        return True
    except Exception as e:
        st.error(f"Error en PlanetScale: {e}")
        return False
