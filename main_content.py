import streamlit as st
import pandas as pd
from logic import load_base, generar_malla_tecnica_pulp, generar_malla_auxiliares_pool

def run_app():
    # ... (Lógica de Login igual a la anterior) ...
    
    df_raw = load_base()
    # ... (Sidebar con mes_sel, ano_sel, etc.) ...
    
    if menu == "📊 Gestión de Mallas":
        tab1, tab2 = st.tabs(["Planta Operativa (T1-T3)", "Auxiliares de Abordaje"])
        DIAS_SEMANA = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]

        with tab1:
            st.header("Malla Técnicos y Masters")
            col_cfg = st.columns(3)
            m_req = col_cfg[0].number_input("Masters x Grupo", 1, 5, 2)
            ta_req = col_cfg[1].number_input("Tec A x Grupo", 1, 15, 7)
            tb_req = col_cfg[2].number_input("Tec B x Grupo", 1, 10, 3)

            with st.expander("📅 Configuración de Grupos Operativos", expanded=True):
                n_map, d_map, t_map = {}, {}, {}
                cols = st.columns(4)
                for i in range(4):
                    with cols[i]:
                        g_id = f"G{i+1}"
                        n_s = st.text_input(f"Nombre {g_id}", f"GRUPO {i+1}", key=f"n_b_{i}")
                        d_s = st.selectbox(f"Descanso {g_id}", DIAS_SEMANA, index=i % 7, key=f"d_b_{i}")
                        es_disp = st.checkbox(f"Disponibilidad {g_id}", value=(i==3), key=f"t_b_{i}")
                        n_map[g_id] = n_s; d_map[n_s] = d_s; t_map[n_s] = "DISP" if es_disp else "ROTA"

            if st.button("⚡ GENERAR MALLA TÉCNICOS/MASTERS"):
                df_f = generar_malla_tecnica_pulp(df_raw, n_map, d_map, t_map, m_req, ta_req, tb_req, ano_sel, mes_num)
                piv = df_f.pivot(index=['Grupo', 'Empleado', 'Cargo'], columns='Label', values='Final')
                cols_ord = sorted(piv.columns, key=lambda x: int(x.split('-')[0]))

                def estilo_b(v):
                    v = str(v)
                    if 'DESC' in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                    if 'T3' in v: return 'background-color: #263238; color: white; font-weight: bold'
                    if 'T1' in v: return 'background-color: #E3F2FD; color: #1565C0; border: 1px solid #166534'
                    if 'T2' in v: return 'background-color: #FFF3E0; color: #EF6C00; border: 1px solid #0369a1'
                    return 'color: gray; font-style: italic'

                st.dataframe(piv[cols_ord].style.map(estilo_b), use_container_width=True)

        with tab2:
            st.header("Malla Auxiliares")
            with st.expander("📅 Configurar Descansos Auxiliares", expanded=True):
                aux_n_map, aux_d_map = {}, {}
                cols_ax = st.columns(5)
                for i in range(5):
                    with cols_ax[i]:
                        n_eq = st.text_input(f"Equipo {i+1}", f"EQ-{chr(65+i)}", key=f"ax_n_{i}")
                        d_eq = st.selectbox(f"Descanso Aux {i+1}", DIAS_SEMANA, index=i, key=f"ax_d_{i}")
                        aux_n_map[i] = n_eq; aux_d_map[n_eq] = d_eq

            if st.button("⚡ GENERAR MALLA AUXILIARES"):
                df_res_ax = generar_malla_auxiliares_pool(df_raw, aux_n_map, aux_d_map, ano_sel, mes_num)
                if df_res_ax is not None:
                    piv_ax = df_res_ax.pivot(index=['Equipo', 'Empleado'], columns='Label', values='Turno')
                    cols_ax_ord = sorted(piv_ax.columns, key=lambda x: int(x.split('-')[0]))

                    def estilo_ax(v):
                        v = str(v)
                        if v == "T1": return 'background-color: #dcfce7; color: #166534'
                        if v == "T2": return 'background-color: #e0f2fe; color: #0369a1'
                        if "DESC" in v: return 'background-color: #EF5350; color: white; font-weight: bold'
                        return 'background-color: #f3f4f6; color: #6b7280'

                    st.dataframe(piv_ax[cols_ax_ord].style.map(estilo_ax), use_container_width=True)
