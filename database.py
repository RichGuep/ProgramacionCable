import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from git import Repo

# Configuración
DB_NAME = "movilgo_data.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

def commit_to_github():
    """Sincroniza el archivo .db con GitHub para que no se pierdan datos."""
    try:
        repo = Repo(".")
        repo.git.add(DB_NAME)
        repo.index.commit("Update database [automated]")
        origin = repo.remote(name='origin')
        origin.push()
        return True
    except Exception as e:
        print(f"Error Git: {e}")
        return False

def read_db(table_name):
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except:
        return None

def save_db(df, table_name):
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        # Intentar persistir en GitHub después de guardar
        commit_to_github()
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
