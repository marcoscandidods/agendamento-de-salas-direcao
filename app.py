import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DO BANCO DE DATOS ---
def init_db():
    conn = sqlite3.connect('agendamentos_fes.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reservas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sala TEXT,
                  data TEXT,
                  horario_inicio TEXT,
                  horario_fim TEXT,
                  evento TEXT,
                  solicitante TEXT,
                  origem TEXT)''')
    conn.commit()
    conn.close()

def salvar_reserva(sala, data_br, inicio, fim, evento, solicitante, origem):
    conn = sqlite3.connect('agendamentos_fes.db')
    c = conn.cursor()
    # Verifica conflito
    c.execute("SELECT * FROM reservas WHERE sala=? AND data=? AND ((horario_inicio BETWEEN ? AND ?) OR (horario_fim BETWEEN ? AND ?))", 
              (sala, data_br, inicio, fim, inicio, fim))
    if c.fetchone():
        conn.close()
        return False
    
    c.execute("INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, solicitante, origem) VALUES (?,?,?,?,?,?,?)",
              (sala, data_br, inicio, fim, evento, solicitante, origem))
    conn.commit()
    conn.close()
    return True

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Sistema de Agendamento - FES/UFAM", layout="wide")
init_db()

st.title("🏨 Agendamento de Salas - Secretaria da Diretoria da FES")
st.markdown("---")

# Sidebar para Novo Agendamento
st.sidebar.header("Novo Agendamento")
with st.sidebar.form("form_reserva"):
    sala = st.selectbox("Selecione a Sala", ["Auditório Rio Amazonas", "Sala de Reunião", "Sala 01 - Térreo", "Sala 02 - Térreo"])
    
    # Ajuste de Data para padrão BR
    data = st.date_input("Data do Evento", format="DD/MM/YYYY")
    
    # Ajuste para meia em meia hora (step=1800 segundos)
    h_inicio = st.time_input("Horário de Início", step=1800)
    h_fim = st.time_input("Horário de Término", step=1800)
    
    evento = st.text_area("Descrição do Evento")
    solicitante = st.text_input("Nome do Solicitante")
    origem = st.selectbox("Origem da Demanda", ["E-mail", "Processo SEI", "Presencial"])
    
    btn_salvar = st.form_submit_button("Confirmar Reserva")

if btn_salvar:
    if evento and solicitante:
        # Formatando a data explicitamente para o banco de dados
        data_formatada = data.strftime('%d/%m/%Y')
        sucesso = salvar_reserva(sala, data_formatada, str(h_inicio), str(h_fim), evento, solicitante, origem)
        if sucesso:
            st.sidebar.success("✅ Reserva confirmada com sucesso!")
        else:
            st.sidebar.error("❌ Conflito de horário! Sala já ocupada.")
    else:
        st.sidebar.warning("⚠️ Preencha todos os campos.")

# Visualização Central
tab1, tab2 = st.tabs(["🗓️ Visualizar Agendamentos", "📊 Relatório Técnico"])

with tab1:
    conn = sqlite3.connect('agendamentos_fes.db')
    df = pd.read_sql_query("SELECT * FROM reservas ORDER BY data, horario_inicio", conn)
    conn.close()
    
    if not df.empty:
        # Renomeando colunas para o usuário
        df.columns = ['ID', 'Local', 'Data', 'Início', 'Fim', 'Descrição', 'Responsável', 'Canal']
        st.dataframe(df.drop(columns=['ID']), use_container_width=True)
    else:
        st.info("Nenhum agendamento realizado até o momento.")

with tab2:
    st.subheader("Integridade e Padronização")
    st.write("Ajustes realizados:")
    st.write("- **Localização:** Data configurada para o padrão brasileiro (DD/MM/AAAA).")
    st.write("- **Granularidade:** Intervalos de tempo ajustados para 30 minutos conforme necessidade da FES.")
