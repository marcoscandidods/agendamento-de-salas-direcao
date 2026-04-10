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

# --- 2. INTERFACE E SESSÃO ---
st.set_page_config(page_title="Gestão de Espaços - Direção", layout="wide")
init_db()

if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year
if 'logado' not in st.session_state: st.session_state.logado = False

# Sidebar Login
with st.sidebar.form("login_form"):
    st.header("🔐 Área Restrita")
    u_input = st.text_input("Usuário")
    s_input = st.text_input("Senha", type="password")
    if st.form_submit_button("Acessar Sistema"):
        if u_input == "diretoriafes" and s_input == "secretariafes2021/2":
            st.session_state.logado = True
            st.rerun()
        else: st.error("Dados inválidos.")

logado = st.session_state.logado
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião", "Salas de Aula"]
salas_de_aula_list = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas[:3] + salas_de_aula_list

if logado:
    st.sidebar.success("Sessão Ativa")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    
    # Backup e Importação
    st.sidebar.markdown("---")
    conn = sqlite3.connect('agendamentos_direcao.db')
    df_total = pd.read_sql_query("SELECT * FROM reservas", conn)
    conn.close()
    if not df_total.empty:
        output_geral = io.BytesIO()
        with pd.ExcelWriter(output_geral, engine='xlsxwriter') as writer:
            for s in todas_as_salas:
                df_s = df_total[df_total['sala'] == s]
                if not df_s.empty: df_s.to_excel(writer, sheet_name=s[:31], index=False)
        st.sidebar.download_button("📥 Backup Geral (Excel)", output_geral.getvalue(), f"Backup_{datetime.now().strftime('%d_%m')}.xlsx")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Novo Agendamento")
    sala_sel = st.sidebar.selectbox("Espaço", todas_as_salas)
    tipo_ag = st.sidebar.radio("Tipo", ["Pontual", "Por Período"])
    origem_sel = st.sidebar.selectbox("Solicitante", ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"])
    esp_ext = st.sidebar.text_input("Especificar Externo") if origem_sel == "EXTERNO" else ""
    meio_sel = st.sidebar.selectbox("Meio", ["E-mail", "SEI", "Presencial", "Outro"])
    sei_n = st.sidebar.text_input("Nº SEI") if meio_sel == "SEI" else ""

    with st.sidebar.form("form_final"):
        if tipo_ag == "Pontual": data_ev = st.date_input("Data")
        else:
            c1, c2 = st.columns(2)
            d_i, d_f = c1.date_input("Início"), c2.date_input("Fim")
            dias = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
        
        h_i = st.time_input("Início", value=time(8, 0), step=1800)
        h_f = st.time_input("Término", value=time(9, 0), step=1800)
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        evento = st.text_area("Finalidade/Evento")
        servidor = st.text_input("Servidor Lançador")
        
        if st.form_submit_button("Confirmar"):
            ori_final = esp_ext if origem_sel == "EXTERNO" else origem_sel
            datas = [data_ev] if tipo_ag == "Pontual" else []
            if tipo_ag == "Por Período":
                m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                ind = [m_d[d] for d in dias]
                curr = d_i
                while curr <= d_f:
                    if curr.weekday() in ind: datas.append(curr)
                    curr += timedelta(days=1)
            for d in datas:
                salvar_reserva(sala_sel, d.strftime('%d/%m/%Y'), str(h_i)[:5], str(h_f)[:5], evento, ori_final, sei_n, st_sel, servidor)
            st.rerun()

# --- 3. COMPONENTES VISUAIS ---
def calendario_compacto(df_sala):
    col_v1, col_v2, col_v3 = st.columns([1, 4, 1])
    if col_v1.button("◀", key=f"p_{df_sala.shape[0]}"):
        st.session_state.mes_ref -= 1
        if st.session_state.mes_ref == 0: st.session_state.mes_ref = 12; st.session_state.ano_ref -= 1
        st.rerun()
    if col_v3.button("▶", key=f"n_{df_sala.shape[1]}"):
        st.session_state.mes_ref += 1
        if st.session_state.mes_ref == 13: st.session_state.mes_ref = 1; st.session_state.ano_ref += 1
        st.rerun()
    
    mes, ano = st.session_state.mes_ref, st.session_state.ano_ref
    nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
    col_v2.markdown(f"<p style='text-align:center; font-weight:bold;'>{nome_mes} / {ano}</p>", unsafe_allow_html=True)
    
    dias_ocupados = {}
    if not df_sala.empty:
        for _, row in df_sala.iterrows():
            try:
                dt = datetime.strptime(row['data'], '%d/%m/%Y')
                if dt.year == ano and dt.month == mes:
                    if dias_ocupados.get(dt.day) != 'Confirmado': dias_ocupados[dt.day] = row['status']
            except: continue

    html_cal = "<table style='width:100%; text-align:center; border-collapse:collapse;'><tr>"
    for d in ['D','S','T','Q','Q','S','S']: html_cal += f"<th style='font-size:10px; color:gray;'>{d}</th>"
    html_cal += "</tr>"
    for semana in calendar.monthcalendar(ano, mes):
        html_cal += "<tr>"
        for i, dia in enumerate(semana):
            if dia == 0: html_cal += "<td></td>"
            else:
                status = dias_ocupados.get(dia)
                bg = "#3D5AFE" if status == 'Confirmado' else ("#FFAB00" if status == 'Pré-agendado' else ("#f0f0f0" if i==0 or i==6 else "white"))
                color = "white" if status == 'Confirmado' else ("black" if status == 'Pré-agendado' else "#444")
                html_cal += f"<td style='background-color:{bg}; color:{color}; border:1px solid #eee; border-radius:4px; font-size:12px; padding:4px;'>{dia}</td>"
        html_cal += "</tr>"
    st.markdown(html_cal + "</table>", unsafe_allow_html=True)

def exibir_tabela(n_sala, mostrar_cal=True):
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=? ORDER BY data DESC", conn, params=(n_sala,))
    conn.close()
    if mostrar_cal: calendario_compacto(df)
    if not df.empty:
        df['dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_f = df[(df['dt'].dt.month == st.session_state.mes_ref) & (df['dt'].dt.year == st.session_state.ano_ref)]
        if not df_f.empty:
            disp = df_f[['status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'servidor_resp']]
            disp.columns = ['Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Lançador']
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#d4edda" if x=="Confirmado" else ("#fff3cd" if x=="Pré-agendado" else "#f8d7da")}', subset=['Status']), use_container_width=True, hide_index=True)

# --- 4. ABA RESUMO SEMESTRAL (SALAS DE AULA) ---
def resumo_semestral():
    st.write("### 🏛️ Mapa de Ocupação Semanal - Salas de Aula")
    conn = sqlite3.connect('agendamentos_direcao.db')
    # Pegamos tudo que não é cancelado
    df = pd.read_sql_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", conn)
    conn.close()

    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    resumo_data = []

    for s in salas_de_aula_list:
        linha = {"Sala": s}
        for d_nome in dias_semana:
            # Lógica para encontrar o que tem nessa sala nesse dia da semana (independente da data real, focando na recorrência)
            m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
            df_sala_dia = df[(df['sala'] == s)]
            # Filtra por dia da semana
            df_sala_dia['dw'] = pd.to_datetime(df_sala_dia['data'], format='%d/%m/%Y').dt.weekday
            eventos = df_sala_dia[df_sala_dia['dw'] == m_d[d_nome]]
            
            if not eventos.empty:
                # Pega os horários e o departamento (origem)
                txt = " | ".join([f"{r['horario_inicio']}-{r['horario_fim']} ({r['origem']})" for _, r in eventos.drop_duplicates(subset=['horario_inicio', 'horario_fim', 'origem']).iterrows()])
                linha[d_nome] = txt
            else:
                linha[d_nome] = "-"
        resumo_data.append(linha)

    df_resumo = pd.DataFrame(resumo_data)
    
    # Estilização de cores por departamento
    def colorir_origem(val):
        if "DA-FES" in val: return 'background-color: #e3f2fd; color: #0d47a1' # Azul
        if "DECON" in val: return 'background-color: #f1f8e9; color: #33691e' # Verde
        if "DEA" in val: return 'background-color: #fff3e0; color: #e65100' # Laranja
        return ''

    st.dataframe(df_resumo.style.applymap(colorir_origem), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.write("#### 🔍 Detalhes por Sala")
    s_detalhe = st.selectbox("Selecione uma sala para ver o calendário detalhado:", ["Selecione..."] + salas_de_aula_list)
    if s_detalhe != "Selecione...":
        exibir_tabela(s_detalhe)

# --- EXECUÇÃO DAS ABAS ---
t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semestral()

st.caption("🚀 Desenvolvido por **Marcos Candido** - Projeto de Extensão do Curso de Engenharia de Software")
