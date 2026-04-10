# --- 3. COMPONENTES VISUAIS ---
def calendario_compacto(df_sala, n_sala):
    # Criamos 3 colunas: as das pontas pequenas para as setas e a do meio maior
    col_v1, col_v2, col_v3 = st.columns([1, 3, 1])
    
    with col_v1:
        if st.button("◀", key=f"p_{n_sala}", use_container_width=True):
            st.session_state.mes_ref -= 1
            if st.session_state.mes_ref == 0: 
                st.session_state.mes_ref = 12
                st.session_state.ano_ref -= 1
            st.rerun()
            
    with col_v3:
        if st.button("▶", key=f"n_{n_sala}", use_container_width=True):
            st.session_state.mes_ref += 1
            if st.session_state.mes_ref == 13: 
                st.session_state.mes_ref = 1
                st.session_state.ano_ref += 1
            st.rerun()
            
    mes, ano = st.session_state.mes_ref, st.session_state.ano_ref
    nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
    
    # O nome do mês centralizado na coluna do meio
    col_v2.markdown(f"<p style='text-align:center; font-weight:bold; font-size:18px; margin-top:5px;'>{nome_mes} / {ano}</p>", unsafe_allow_html=True)
    
    # ... (restante do código do calendário segue igual abaixo)
