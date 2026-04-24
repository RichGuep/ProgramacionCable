import pandas as pd
import requests
import base64
import io
import streamlit as st

def guardar_excel_en_github(df, file_name):
    """Sube un DataFrame de Pandas como Excel a GitHub usando su API."""
    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["REPO_NAME"]
    url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
    
    # 1. Convertir el DataFrame a un archivo Excel en memoria
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    
    # Codificar el contenido en Base64 (Requisito de GitHub API)
    content_encoded = base64.b64encode(output.getvalue()).decode()

    # 2. Verificar si el archivo ya existe para obtener su 'sha' (necesario para actualizar)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get("sha") if get_res.status_code == 200 else None

    # 3. Preparar el envío (PUT)
    data = {
        "message": f"Actualización automatizada de {file_name}",
        "content": content_encoded,
        "branch": "main" # Asegúrate de que tu rama principal sea main
    }
    if sha:
        data["sha"] = sha

    put_res = requests.put(url, json=data, headers=headers)
    
    if put_res.status_code in [200, 201]:
        return True
    else:
        st.error(f"Error GitHub: {put_res.json().get('message')}")
        return False
