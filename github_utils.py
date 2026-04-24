import pandas as pd
import requests
import base64
import io
import streamlit as st

def guardar_excel_en_github(df, file_name):
    token = st.secrets["GITHUB_TOKEN"]
    repo = "tu_usuario/tu_repositorio"  # Cambia esto
    url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
    
    # 1. Convertir DF a bytes de Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    content = base64.b64encode(output.getvalue()).decode()

    # 2. Obtener el SHA del archivo si ya existe (para poder sobrescribir)
    headers = {"Authorization": f"token {token}"}
    res = requests.get(url, headers=headers)
    sha = res.json().get("sha") if res.status_code == 200 else None

    # 3. Subir/Actualizar
    data = {
        "message": f"Update {file_name} from MovilGo App",
        "content": content,
        "branch": "main"
    }
    if sha: data["sha"] = sha

    requests.put(url, json=data, headers=headers)
