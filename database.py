import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os

# Configuración básica
DB_NAME = "movilgo_data.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

def read_db(table_name):
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception as e:
        return None

def save_db(df, table_name):
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
