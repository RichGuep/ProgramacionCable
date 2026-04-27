import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
from git import Repo
from logic import load_base 

# Configuración
DB_NAME = "movilgo_data.db"
engine = create_engine(f"sqlite:///{DB_NAME}")

def commit_to_github():
    try:
        # 1. Cargar credenciales desde los Secrets
        token = st.secrets["GITHUB_TOKEN"]
        user = st.secrets["GITHUB_USER"]
        repo_name = st.secrets["GITHUB_REPO"]
        
        # 2. Configurar la URL con permisos
        remote_url = f"https://{user}:{token}@github.com/{user}/{repo_name}.git"
        
        repo = Repo(".")
        
        # 3. Configurar usuario para el commit
        with repo.config_writer() as cw:
            cw.set_value("user", "name", "MovilGo Admin")
            cw.set_value("user", "email", "richard@movilgo.com")

        # 4. Añadir el archivo .db y subirlo
        if os.path.exists(DB_NAME):
            repo.git.add(DB_NAME)
            repo.index.commit("Sincronización de Base de Datos")
            
            # Verificar si existe el remoto, si no, crearlo
            if 'origin_sync' in [r.name for r in repo.remotes]:
                repo.delete_remote('origin_sync')
            
            origin = repo.create_remote('origin_sync', remote_url)
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
        # Guardar en el archivo local de la app
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        
        # ¡ESTA ES LA LÍNEA CLAVE! Envía el archivo a tu GitHub
        commit_to_github() 
        
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
