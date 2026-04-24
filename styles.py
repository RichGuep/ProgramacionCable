# --- LÓGICA DE LOGIN ---
    if not st.session_state['auth']:
        # Estilos personalizados para centrar todo y agrandar el logo
        st.markdown("""
            <style>
                .login-container {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding-top: 2rem;
                }
                .stImage > img {
                    display: block;
                    margin-left: auto;
                    margin-right: auto;
                    width: 450px !important;  /* Logo más grande */
                }
                .brand-title {
                    text-align: center;
                    color: #064e3b;
                    font-size: 42px;
                    font-weight: bold;
                    margin-top: 10px;
                    margin-bottom: 5px;
                }
                .brand-subtitle {
                    text-align: center;
                    color: #666;
                    font-size: 18px;
                    margin-bottom: 2rem;
                }
                /* Estilo para el contenedor del formulario */
                [data-testid="stForm"] {
                    border: 1px solid #ddd;
                    padding: 2rem;
                    border-radius: 15px;
                    background-color: #f9f9f9;
                    max-width: 450px;
                    margin: 0 auto;
                }
            </style>
        """, unsafe_allow_html=True)

        # Contenedor visual
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        # 1. Logo Centrado y Grande
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH)
        
        # 2. Título debajo del Logo
        st.markdown('<div class="brand-title">MovilGo Admin</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-subtitle">Gestión de Operaciones Green Móvil</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 3. Formulario de Login
        with st.form("Login"):
            u = st.text_input("Usuario Corporativo")
            p = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("INGRESAR AL PANEL", use_container_width=True)
            
            if submit:
                user_match = df_users[(df_users['Correo'] == u) & (df_users['Password'].astype(str) == p)]
                if u == "richard.guevara@greenmovil.com.co" and p == "Admin2026":
                    st.session_state['auth'], st.session_state['rol'] = True, "Admin"
                    st.rerun()
                elif not user_match.empty:
                    st.session_state['auth'], st.session_state['rol'] = True, user_match.iloc[0]['Rol']
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")
        return
