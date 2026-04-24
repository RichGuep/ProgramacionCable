import streamlit as st

def estilo_malla(val):
    """Aplica colores específicos a las celdas de la malla técnica."""
    color = ""
    background = ""
    if val == "T1":
        background = "#d1fae5"
        color = "#065f46"
    elif val == "T2":
        background = "#fef3c7"
        color = "#92400e"
    elif val == "T3":
        background = "#fee2e2"
        color = "#991b1b"
    elif "DESC" in str(val):
        background = "#f3f4f6"
        color = "#374151"
    elif "APOYO" in str(val):
        background = "#e0e7ff"
        color = "#3730a3"
    return f"background-color: {background}; color: {color}; border: 1px solid #e5e7eb;"

def estilo_ax(val):
    """Estilos específicos para auxiliares."""
    background = ""
    color = ""
    if val == "T1":
        background = "#ecfdf5"
        color = "#047857"
    elif val == "T2":
        background = "#fffbeb"
        color = "#b45309"
    elif val == "DISPONIBILIDAD":
        background = "#eff6ff"
        color = "#1d4ed8"
    elif "DESC" in str(val):
        background = "#f9fafb"
        color = "#6b7280"
    return f"background-color: {background}; color: {color};"

def get_login_styles():
    """CSS para el Login centrado y corporativo."""
    return """
    <style>
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding-top: 1rem;
        }
        .stImage > img {
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 480px !important;
            max-width: 100%;
        }
        .brand-title {
            text-align: center;
            color: #064e3b;
            font-size: 45px;
            font-weight: bold;
            margin-top: -15px;
        }
        .brand-subtitle {
            text-align: center;
            color: #4b5563;
            font-size: 20px;
            margin-bottom: 2.5rem;
        }
        [data-testid="stForm"] {
            border: 1px solid #e5e7eb;
            padding: 3rem;
            border-radius: 25px;
            background-color: #ffffff;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
            max-width: 500px;
            margin: 0 auto;
        }
        .stButton > button {
            background-color: #10b981 !important;
            color: white !important;
            font-size: 18px !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            height: 3.5rem !important;
            width: 100% !important;
        }
    </style>
    """

def apply_global_styles():
    """Estilos globales para la App."""
    st.markdown("""
        <style>
            .stApp { background-color: #f8fafc; }
            [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
        </style>
    """, unsafe_allow_html=True)
