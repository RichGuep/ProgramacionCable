import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from git import Repo
from logic import load_base 

DB_NAME = "movilgo_data.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

def commit_to_github():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        user = st.secrets["GITHUB_USER"]
        repo_name = st.secrets["GITHUB_REPO"]
        remote_url = f"https://{user}:{token}@github.com/{user}/{repo_name}.git"
        repo = Repo(".")
        with repo.config_writer() as cw:
            cw.set_value("user", "name", "Streamlit App")
            cw.set_value("user", "email", "admin@movilgo.com")
        if os.path.exists(DB_NAME):
            repo.git.add(DB_NAME)
            repo.index.commit("Update DB")
            origin = repo.remotes.origin if 'origin' in repo.remotes else repo.create_remote('origin', remote_url)
            origin.push('main')
        return True
    except Exception as e:
        print(f"Error Git: {e}")
        return False

def read_db(table_name):
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    except Exception as e:
        if "no such table" in str(e).lower():
            if table_name == "empleados":
                df_ini = load_base()
                save_db(df_ini, "empleados")
                return df_ini
            elif table_name == "usuarios":
                df_admin = pd.DataFrame([{"Nombre": "Richard", "Correo": "richard.guevara@greenmovil.com.co", "Rol": "Admin", "Password": "Admin2026"}])
                save_db(df_admin, "usuarios")
                return df_admin
        return None

def save_db(df, table_name):
    try:
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        # commit_to_github() # Mantenlo comentado con # hasta que la app abra
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
