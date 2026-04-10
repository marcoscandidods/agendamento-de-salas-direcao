import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io

# --- 1. CONFIGURAÇÃO E BANCO DE DATOS ---
def init_db():
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reservas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  sala TEXT,
                  data TEXT,
                  horario_inicio TEXT,
                  horario_fim TEXT,
                  evento TEXT,
                  origem TEXT,
                  numero_sei TEXT,
                  status TEXT,
                  servidor_resp TEXT)''')
    conn.commit()
    conn.close()

def verificar_conflito(sala, data, inicio, fim):
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("""SELECT * FROM reservas 
                 WHERE sala=? AND data=? AND status != 'Cancelado'
                 AND ((horario_inicio < ? AND horario_fim > ?))""", 
              (sala, data, fim, inicio))
    conflito = c.fetchone()
    conn.close()
    return conflito

def salvar_reserva(sala, data, inicio, fim, evento, origem, sei, status, servidor):
    if status != "Cancelado" and verificar_conflito(sala, data, inicio, fim):
        return False
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("""INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, origem, numero_sei, status, servidor_resp) 
                 VALUES (?,?,?,?,?,?,?,?,?)""", (sala, data, inicio, fim, evento, origem, sei, status, servidor))
    conn.commit()
    conn.close()
    return True

def deletar_registro(id_registro):
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("DELETE FROM reservas WHERE id=?", (id_registro,))
    conn.commit()
    conn.close()

# --- 2. INTERFACE ---
st.set_page_config(page_title="Sistema de Agendamento - Direção", layout="wide")
init_db()

st.title("📅 Gestão de Espaços - Direção")

if 'logado' not in st.session_state:
    st.session_state.logado = False

# Sidebar Login
with st.sidebar.form("login_form"):
    st.header("🔐 Área Restrita")
    u_input = st.text_input("Usuário")
    s_input = st.text_input("Senha", type="password")
    if st.form_submit_button("Acessar Sistema"):
        if u_input == "diretoriafes" and s_input == "secretariafes2021/2":
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Dados inválidos.")

logado = st.session_state.logado
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião"]
salas_de_aula = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas + salas_de_aula

if logado:
    st.sidebar.success("Sessão Ativa")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    
    st.sidebar.markdown("---")
    with st.sidebar.expander("🗑️ Remover Registros"):
        sala_l = st.selectbox("Sala", todas_as_salas, key="l_s")
        conn = sqlite3.connect('agendamentos_direcao.db')
        df_l = pd.read_sql_query("SELECT id, data, evento FROM reservas WHERE sala=?", conn, params=(sala_l,))
        conn.close()
        if not df_l.empty:
            opc = {f"ID {row['id']} | {row['data']}": row['id'] for _, row in df_l.iterrows()}
            it = st.selectbox("Item", list(opc.keys()))
            if st.button("EXCLUIR"):
                deletar_registro(opc[it])
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Novo Agendamento")
    
    sala_sel = st.sidebar.selectbox("Espaço", todas_as_salas)
    tipo_ag = st.sidebar.radio("Tipo", ["Pontual", "Por Período"])
    
    origem_opc = ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"]
    origem_sel = st.sidebar.selectbox("Solicitante", origem_opc)
    esp_ext = ""
    if origem_sel == "EXTERNO":
        esp_ext = st.sidebar.text_input("Especificar Externo")
    
    meio_opc = ["E-mail", "SEI", "Presencial", "Outro"]
    meio_sel = st.sidebar.selectbox("Meio da solicitação", meio_opc)
    sei_n = ""
    if meio_sel == "SEI":
        sei_n = st.sidebar.text_input("Nº Processo SEI")

    with st.sidebar.form("form_final"):
        if tipo_ag == "Pontual":
            data_ev = st.date_input("Data", format="DD/MM/YYYY")
            d_i, d_f, dias = None, None, []
        else:
            c1, c2 = st.columns(2)
            d_i = c1.date_input("Início", format="DD/MM/YYYY")
            d_f = c2.date_input("Fim", format="DD/MM/YYYY")
            dias = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
            data_ev = None

        # AJUSTE DE HORÁRIO: Limitado entre 08:00 e 22:00
        h_i = st.time_input("Início", value=time(8, 0), step=1800)
        h_f = st.time_input("Término", value=time(9, 0), step=1800)
        
        # Validação simples de horário no front-end
        if h_i < time(8, 0) or h_i > time(22, 0):
            st.warning("Horário de funcionamento: 08h às 22h")
        
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        
        conf_c = True
        if st_sel == "Cancelado":
            conf_c = st.checkbox("Confirmar cancelamento")
        
        evento = st.text_area("Finalidade/Evento")
        servidor = st.text_input("Servidor Lançador")
        
        if st.form_submit_button("Confirmar Agendamento"):
            if st_sel == "Cancelado" and not conf_c:
                st.error("Confirme o cancelamento.")
            elif h_i < time(8,0) or h_f > time(22,0):
                st.error("Erro: Agendamentos apenas entre 08:00 e 22:00.")
            elif evento and servidor:
                ori_final = esp_ext if origem_sel == "EXTERNO" else origem_sel
                datas_lista = []
                if tipo_ag == "Pontual":
                    datas_lista = [data_ev]
                else:
                    m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                    ind = [m_d[d] for d in dias]
                    curr = d_i
                    while curr <= d_f:
                        if curr.weekday() in ind: datas_lista.append(curr)
                        curr += timedelta(days=1)
                
                for d in datas_lista:
                    salvar_reserva(sala_sel, d.strftime('%d/%m/%Y'), str(h_i), str(h_f), evento, ori_final, sei_n, st_sel, servidor)
                st.rerun()

# --- 3. FUNÇÃO DE CALENDÁRIO EM GRADE (SEMANAL) ---
def calendario_grade_ocupacao(df_sala):
    hoje = datetime.now()
    ano, mes = hoje.year, hoje.month
    nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
    
    st.write(f"🔍 **Disponibilidade - {nome_mes}/{ano}**")
    
    # Mapeia dias ocupados
    dias_ocupados = {}
    if not df_sala.empty:
        for _, row in df_sala.iterrows():
            try:
                dt = datetime.strptime(row['data'], '%d/%m/%Y')
                if dt.year == ano and dt.month == mes:
                    # Prioriza 'Confirmado' na cor do calendário
                    if dias_ocupados.get(dt.day) != 'Confirmado':
                        dias_ocupados[dt.day] = row['status']
            except: continue

    # Configuração da Grade (7 colunas para os dias da semana)
    dias_semana_abrev = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    cabecalho = st.columns(7)
    for i, nome_d in enumerate(dias_semana_abrev):
        cabecalho[i].markdown(f"<p style='text-align:center; font-weight:bold; margin-bottom:0;'>{nome_d}</p>", unsafe_allow_html=True)

    # Lógica de preenchimento do calendário
    cal = calendar.monthcalendar(ano, mes)
    for semana in cal:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            if dia == 0:
                cols[i].write("") # Espaço vazio para dias fora do mês
            else:
                status_dia = dias_ocupados.get(dia)
                cor = "#eeeeee" # Cinza (Livre)
                texto = "#999999"
                
                if status_dia == 'Confirmado':
                    cor, texto = "#3D5AFE", "white"
                elif status_dia == 'Pré-agendado':
                    cor, texto = "#FFAB00", "black"
                
                cols[i].markdown(f"""
                    <div style='text-align:center; background-color:{cor}; color:{texto}; 
                    border-radius:4px; padding:5px; margin:2px; font-size:14px; font-weight:bold;'>
                    {dia}
                    </div>
                """, unsafe_allow_html=True)

# --- 4. VISUALIZAÇÃO ---
def exibir_tabela(n_sala):
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=? ORDER BY data DESC", conn, params=(n_sala,))
    conn.close()

    # Exibe o calendário em grade no topo
    calendario_grade_ocupacao(df)
    st.markdown("<br>", unsafe_allow_html=True)

    if not df.empty:
        df_display = df.copy()
        df_display = df_display[['status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'numero_sei', 'servidor_resp']]
        df_display.columns = ['Status', 'Data', 'Início', 'Fim', 'Descrição', 'Solicitante', 'Nº SEI', 'Lançado por']
        
        cores = {'Confirmado': '#d4edda', 'Pré-agendado': '#fff3cd', 'Cancelado': '#f8d7da'}
        st.dataframe(df_display.style.map(lambda x: f'background-color: {cores.get(x, "#ffffff")}; color: black', subset=['Status']), 
                     use_container_width=True, hide_index=True)
        
        if logado:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                df_display.to_excel(wr, index=False)
            st.download_button(f"📥 Excel - {n_sala}", out.getvalue(), f"{n_sala}.xlsx", key=f"d_{n_sala}")
    else:
        st.info(f"Sem agendamentos para {n_sala}.")

st.subheader("🗓️ Cronograma Principal")
t1, t2, t3 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")

st.markdown("---")
s_ext = st.selectbox("Salas de Aula:", ["Selecione..."] + salas_de_aula)
if s_ext != "Selecione...": exibir_tabela(s_ext)

st.markdown("---")
st.caption("🚀 Desenvolvido por **Marcos Candido** - Projeto de Extensão do Curso de Engenharia de Software")
