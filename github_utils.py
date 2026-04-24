import pandas as pd
import requests
import base64
import io
import streamlit as st

def leer_excel_de_github(file_name):
    """
    Busca un archivo en el repositorio de GitHub y lo descarga 
    para convertirlo en un DataFrame de Pandas.
    """
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        res = requests.get(url, headers=headers)
        
        if res.status_code == 200:
            # GitHub devuelve el contenido en base64, debemos decodificarlo
            content = base64.b64decode(res.json()["content"])
            return pd.read_excel(io.BytesIO(content))
        else:
            # Si el archivo no existe (ej. la primera vez), devolvemos None
            return None
    except Exception as e:
        st.error(f"Error al leer desde GitHub: {e}")
        return None

def guardar_excel_en_github(df, file_name):
    """
    Convierte un DataFrame a Excel y lo sube a GitHub. 
    Si el archivo ya existe, lo actualiza usando su identificador SHA.
    """
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
        
        # 1. Convertir el DataFrame a bytes de Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        
        # Codificar en base64 para la API de GitHub
        content_encoded = base64.b64encode(output.getvalue()).decode()

        # 2. Configurar headers de autenticación
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

        # 3. Obtener el SHA (necesario para actualizar archivos existentes)
        get_res = requests.get(url, headers=headers)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None

        # 4. Preparar datos para el envío
        data = {
            "message": f"Actualización automatizada: {file_name} [{datetime.now().strftime('%Y-%m-%d %H:%M')}]",
            "content": content_encoded,
            "branch": "main"  # Asegúrate de que tu rama sea 'main'
        }
        if sha:
            data["sha"] = sha

        # 5. Realizar la petición PUT
        put_res = requests.put(url, json=data, headers=headers)
        
        if put_res.status_code in [200, 201]:
            return True
        else:
            error_msg = put_res.json().get('message', 'Error desconocido')
            st.error(f"Error al guardar en GitHub: {error_msg}")
            return False
            
    except Exception as e:
        st.error(f"Error crítico en la conexión con GitHub: {e}")
        return False
