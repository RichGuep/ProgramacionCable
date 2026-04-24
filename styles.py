import streamlit as st

def apply_custom_styles():
    st.set_page_config(page_title="MovilGo Pro | Green Móvil", layout="wide", page_icon="🚌")
    st.markdown("""
        <style>
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
        .main { background-color: #f8fafc; }
        .login-card {
            background-color: white; padding: 3.5rem; border-radius: 24px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15); border: 1px solid #e2e8f0;
            text-align: center; max-width: 500px; margin: 100px auto;
        }
        .brand-title { color: #064e3b; font-size: 2.6rem; font-weight: 850; margin-top: 20px; text-align: center; letter-spacing: -1px; }
        .brand-subtitle { color: #64748b; font-size: 1.1rem; margin-bottom: 30px; text-align: center; }
        .stButton>button {
            width: 100%; border-radius: 12px; background: linear-gradient(90deg, #10b981 0%, #059669 100%);
            color: white; font-weight: 700; height: 3.5rem; border: none; transition: 0.3s;
        }
        .stButton>button:hover { box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4); transform: translateY(-2px); }
        </style>
    """, unsafe_allow_html=True)

def estilo_malla(v):
    v = str(v)
    if 'DESC' in v: return 'background-color: #EF5350; color: white; font-weight: bold'
    if 'T3' in v: return 'background-color: #263238; color: white; font-weight: bold'
    if 'T1' in v: return 'background-color: #E3F2FD; color: #1565C0; border: 1px solid #166534'
    if 'T2' in v: return 'background-color: #FFF3E0; color: #EF6C00; border: 1px solid #0369a1'
    return 'color: gray; font-style: italic'

def estilo_ax(v):
    v = str(v)
    if v == "T1": return 'background-color: #dcfce7; color: #166534'
    if v == "T2": return 'background-color: #e0f2fe; color: #0369a1'
    if "DESC" in v: return 'background-color: #EF5350; color: white; font-weight: bold'
    return 'background-color: #f3f4f6; color: #6b7280'
