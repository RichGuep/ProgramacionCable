import pandas as pd
import requests
import base64
import io
import streamlit as st
from datetime import datetime

def leer_excel_de_github(file_name):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content = base64.b64decode(res.json()["content"])
            return pd.read_excel(io.BytesIO(content))
        return None
    except: return None

def guardar_excel_en_github(df, file_name):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["REPO_NAME"]
        url = f"https://api.github.com/repos/{repo}/contents/{file_name}"
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        content_encoded = base64.b64encode(output.getvalue()).decode()
        headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
        get_res = requests.get(url, headers=headers)
        sha = get_res.json().get("sha") if get_res.status_code == 200 else None
        data = {"message": f"Update {file_name} {datetime.now()}", "content": content_encoded, "branch": "main"}
        if sha: data["sha"] = sha
        res = requests.put(url, json=data, headers=headers)
        return res.status_code in [200, 201]
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return False
