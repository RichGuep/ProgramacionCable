import streamlit as st
import pandas as pd
import plotly.express as px
import processor

# ... (Mantener estilos y login igual)

# --- APP LAYOUT ---
df = processor.cargar_datos_pantalla()
u_info = st.session_state.user_info
is_admin = (u_info.get('correo') == processor.ADMIN_EMAIL or str(u_info.get('rol')).lower() == 'admin')

# Añadimos la pestaña de RRHH
tabs = st.tabs(["📊 ESTADÍSTICAS", "🚀 GESTIÓN PIR", "📋 SEGUIMIENTO", "📈 MÉTRICAS RRHH", "⚙️ CONFIG"] if is_admin else ["📊 ESTADÍSTICAS", "🚀 GESTIÓN PIR", "📋 SEGUIMIENTO"])

# ... (Filtros Sidebar igual)

with tabs[0]: # Estadísticas
    # Agregamos métrica de Rotación Operativa (Cambios vs Total)
    try:
        gestiones = processor.conn.read(worksheet="GESTION_OPERATIVA", ttl=0)
        total_serv = len(df)
        cambios = len(gestiones)
        rotacion_ops = (cambios / total_serv) * 100 if total_serv > 0 else 0
        st.metric("Índice de Rotación Operativa", f"{rotacion_ops:.1f}%", help="Porcentaje de servicios modificados respecto al total")
    except: pass

with tabs[3] if is_admin else None: # MÉTRICAS RRHH
    if is_admin:
        st.subheader("📈 Control de Descansos y Compensatorios")
        st.info("Esta tabla analiza quién trabajó los fines de semana y si tiene días libres asignados entre semana.")
        
        df_rrhh = processor.calcular_metricas_rrhh(df)
        
        if not df_rrhh.empty:
            # Filtros rápidos para RRHH
            c1, c2 = st.columns(2)
            tipo_filtro = c1.multiselect("Filtrar por Contrato:", df_rrhh['Contrato'].unique(), default=df_rrhh['Contrato'].unique())
            comp_filtro = c2.selectbox("¿Ver solo con compensatorio pendiente?", ["Todos", "Pendientes (No descansó entre semana)"])
            
            df_display = df_rrhh[df_rrhh['Contrato'].isin(tipo_filtro)]
            if "Pendientes" in comp_filtro:
                df_display = df_display[df_display['Compensatorio'] == "NO"]
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Gráfico de Sábados
            st.plotly_chart(px.bar(df_display, x="Operador", y="Sábados Trabajados", color="Contrato", title="Distribución de Sábados Laborados"), use_container_width=True)
        else:
            st.warning("No hay datos suficientes para calcular métricas de RRHH.")

# ... (Resto de pestañas igual)
