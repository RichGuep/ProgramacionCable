import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import processor

ADMIN_EMAIL = "richard.guevara@greenmovil.com.co"
st.set_page_config(page_title="NexOp | Green Móvil", layout="wide", page_icon="⚡")

# --- ESTILO CORPORATIVO ---
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/century-gothic');
    * { font-family: 'Century Gothic', sans-serif !important; }
    .stApp { background-color: #fcfdfc; }
    .main-header { background: linear-gradient(90deg, #1a531f 0%, #2e7d32 100%); padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 25px; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #1a531f; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
    .stTabs [aria-selected="true"] { background-color: #1a531f !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

if "auth" not in st.session_state: st.session_state.auth = False

# --- LOGIN ---
if not st.session_state.auth:
    c2 = st.columns([1,1.2,1])[1]
    with c2:
        st.markdown('<div class="main-header"><h1>NexOp Access</h1></div>', unsafe_allow_html=True)
        u = st.text_input("Correo").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("INGRESAR", use_container_width=True):
            users = processor.obtener_usuarios()
            if u in users and str(users[u].get('pw')) == p:
                st.session_state.auth = True; st.session_state.user_info = users[u]; st.rerun()
            else: st.error("Acceso Denegado")
    st.stop()

# --- POPUP GESTIÓN ---
@st.dialog("🛠️ Gestión Operativa (PIR)", width="large")
def ventana_gestion(viaje):
    empresa = viaje.get('empresa', 'ZMO V')
    prefijo = "Z63-" if empresa == "ZMO III" else "Z67-"
    df_b = processor.conn.read(worksheet="VEHICULOS", ttl=0)
    lista_b = ["N/A"] + (df_b[df_b['Código'].astype(str).str.startswith(prefijo)]['Código'].tolist() if not df_b.empty else [])
    
    try: idx_def = lista_b.index(str(viaje['bus_prog']))
    except: idx_def = 0

    with st.form("form_g"):
        c1, c2 = st.columns(2)
        bus_r = c1.selectbox("Móvil Real:", options=lista_b, index=idx_def)
        mot_m = c1.selectbox("Motivo Móvil:", ["Operación Normal", "RETOMA", "Falta movil", "Bus varado", "Accidente"])
        ope_r = c2.text_input("Operador Real:", value=viaje['ope_prog'])
        mot_o = c2.selectbox("Motivo Operador:", ["Operación Normal", "Falta operador", "Enfermo", "No llegó"])
        elim_k = c2.toggle("¿Eliminar KM?")
        obs = st.text_area("Observaciones Finales")
        if st.form_submit_button("✅ GUARDAR CAMBIOS", use_container_width=True):
            if processor.aplicar_gestion_servicio({"servbus": viaje['servbus'], "bus_prog": viaje['bus_prog'], "bus_real": bus_r, "motivo_movil": mot_m, "ope_prog": viaje['ope_prog'], "ope_real": ope_r, "motivo_ope": mot_o, "eliminar_km": "SI" if elim_k else "NO", "obs_final": obs}, st.session_state.user_info['nombre']):
                st.success("Guardado"); st.rerun()

# --- APP LAYOUT ---
st.markdown('<div class="main-header"><h1>NexOp | Green Móvil</h1></div>', unsafe_allow_html=True)
df = processor.cargar_datos_pantalla()
u_info = st.session_state.user_info
is_admin = (u_info.get('correo') == ADMIN_EMAIL or str(u_info.get('rol')).lower() == 'admin')

tabs = st.tabs(["📊 ESTADÍSTICAS", "🚀 GESTIÓN PIR", "📋 SEGUIMIENTO", "📈 RRHH", "⚙️ CONFIG"] if is_admin else ["📊 ESTADÍSTICAS", "🚀 GESTIÓN PIR", "📋 SEGUIMIENTO"])

if not df.empty:
    f_sel = st.sidebar.selectbox("📅 Día:", sorted(df['fecha'].unique().tolist()))
    df_f = df[df['fecha'] == f_sel].copy()

    with tabs[0]: # ESTADÍSTICAS
        c1, c2, c3 = st.columns(3)
        c1.metric("Servicios", len(df_f))
        c2.metric("Buses", len(df_f['bus_prog'].unique()))
        with st.expander("🔍 CONSULTAR LISTADO POR RUTA"):
            st.dataframe(df_f.groupby(['ruta', 'tabla'])['bus_prog'].first().reset_index(), use_container_width=True, hide_index=True)
        st.plotly_chart(px.bar(df_f.groupby('ruta').size().reset_index(name='Cant'), x='ruta', y='Cant', color_discrete_sequence=['#1a531f']), use_container_width=True)

    with tabs[1]: # GESTIÓN PIR
        cols = ['timeOrigin', 'ruta', 'tabla', 'bus_prog', 'ope_prog', 'empresa', 'servbus']
        sel = st.dataframe(df_f[cols], use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")
        if sel.selection.rows: ventana_gestion(df_f.iloc[sel.selection.rows[0]])

    if is_admin:
        with tabs[3]: # RRHH
            st.subheader("📈 Control de Descansos y Compensatorios")
            df_rr = processor.calcular_metricas_rrhh(df)
            st.dataframe(df_rr, use_container_width=True, hide_index=True)
            st.plotly_chart(px.bar(df_rr, x="Operador", y="Sábados", color="Compensatorio"), use_container_width=True)

if is_admin:
    with tabs[-1]: # CONFIG
        with st.form("d_f"):
            c1, c2 = st.columns(2)
            if st.form_submit_button("🚀 SINCRONIZAR"):
                processor.sincronizar_semana_por_dias(str(c1.date_input("I")), str(c2.date_input("F")))

st.sidebar.button("Cerrar Sesión", on_click=lambda: st.session_state.update({"auth": False}))
