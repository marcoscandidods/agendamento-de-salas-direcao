import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO DO BANCO DE DATOS ---
def init_db():
    # Nome do arquivo de banco de dados mais genérico
    conn = sqlite3.connect('agendamentos_direcao.db')
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
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    # Verifica conflito de horário
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
# Título da aba do navegador alterado
st.set_page_config(page_title="Sistema de Agendamento - Direção", layout="wide")
init_db()

# Título principal sem FES/UFAM
st.title("🏨 Gestão de Espaços - Direção")
st.markdown("---")

# Sidebar para Novo Agendamento
st.sidebar.header("Novo Agendamento")
with st.sidebar.form("form_reserva"):
    # Nomes das salas mantidos de forma genérica
    sala = st.selectbox("Selecione o Espaço", ["Auditório Principal", "Sala de Reunião", "Sala Técnica 01", "Sala Técnica 02"])
    
    # Data em formato brasileiro
    data = st.date_input("Data do Evento", format="DD/MM/YYYY")
    
    # Intervalo de 30 minutos
    h_inicio = st.time_input("Horário de Início", step=1800)
    h_fim = st.time_input("Horário de Término", step=1800)
    
    evento = st.text_area("Descrição do Evento/Finalidade")
    solicitante = st.text_input("Nome do Responsável")
    origem = st.selectbox("Origem da Demanda", ["E-mail", "Sistema Interno", "Presencial"])
    
    btn_salvar = st.form_submit_button("Confirmar Reserva")

if btn_salvar:
    if evento and solicitante:
        data_formatada = data.strftime('%d/%m/%Y')
        sucesso = salvar_reserva(sala, data_formatada, str(h_inicio), str(h_fim), evento, solicitante, origem)
        if sucesso:
            st.sidebar.success("✅ Reserva confirmada com sucesso!")
        else:
            st.sidebar.error("❌ Conflito de horário! Espaço já ocupado.")
    else:
        st.sidebar.warning("⚠️ Preencha todos os campos obrigatórios.")

# Visualização Central
tab1, tab2 = st.tabs(["🗓️ Visualizar Agendamentos", "📊 Informações do Sistema"])

with tab1:
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas ORDER BY data, horario_inicio", conn)
    conn.close()
    
    if not df.empty:
        df.columns = ['ID', 'Espaço', 'Data', 'Início', 'Fim', 'Descrição', 'Responsável', 'Canal']
        st.dataframe(df.drop(columns=['ID']), use_container_width=True)
    else:
        st.info("Nenhum agendamento registrado até o momento.")

with tab2:
    st.subheader("Controle de Integridade")
    st.write("Sistema desenvolvido para garantir a organização e segurança dos dados de agendamento.")
    st.write("- **Validação Automática:** Impede sobreposição de horários no mesmo local.")
    st.write("- **Persistência:** Dados armazenados em banco de dados relacional.")
    st.write("- **Padronização:** Formatos de data e hora ajustados para a rotina administrativa.")
