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
        
        # 2. Configurar la URL con permisos (ghp_... @github.com)
        remote_url = f"https://{token}@github.com/{user}/{repo_name}.git"
        
        # 3. Acceder al repositorio local en el servidor
        repo = Repo(".")
        
        # 4. Configurar identidad (necesario para hacer commits)
        with repo.config_writer() as cw:
            cw.set_value("user", "name", "MovilGo Admin")
            cw.set_value("user", "email", "admin@movilgo.com")

        # 5. Añadir y guardar cambios localmente
        if os.path.exists(DB_NAME):
            repo.git.add(DB_NAME)
            # Solo hacer commit si hay cambios reales para evitar errores
            if repo.is_dirty(untracked_files=True):
                repo.index.commit("Actualización de base de datos")
            
            # 6. Forzar la subida a GitHub
            # Intentamos limpiar el remoto 'origin' si existe para evitar conflictos
            try:
                repo.delete_remote('origin_sync')
            except:
                pass
                
            origin = repo.create_remote('origin_sync', remote_url)
            origin.push('main') # Asegúrate que tu rama se llame 'main'
            return True
    except Exception as e:
        # Esto imprimirá el error exacto en la consola negra (Logs)
        st.error(f"Error al sincronizar con GitHub: {e}")
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
        # Guarda el archivo en el disco del servidor
        df.to_sql(table_name, engine, if_exists='replace', index=False)
        # Activa la sincronización con tu repositorio
        commit_to_github()
        return True
    except Exception as e:
        st.error(f"Error SQLite: {e}")
        return False
