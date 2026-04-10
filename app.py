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

# --- 2. INTERFACE E CONTROLE DE NAVEGAÇÃO ---
st.set_page_config(page_title="Gestão de Espaços - Direção", layout="wide")
init_db()

# Inicializa o estado do mês e ano se não existir
if 'mes_ref' not in st.session_state:
    st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state:
    st.session_state.ano_ref = datetime.now().year

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
    
    # Backup e Importação
    st.sidebar.markdown("---")
    st.sidebar.subheader("📦 Backup e Importação")
    
    conn = sqlite3.connect('agendamentos_direcao.db')
    df_total = pd.read_sql_query("SELECT * FROM reservas", conn)
    conn.close()
    
    if not df_total.empty:
        output_geral = io.BytesIO()
        with pd.ExcelWriter(output_geral, engine='xlsxwriter') as writer:
            for s in todas_as_salas:
                df_s = df_total[df_total['sala'] == s]
                if not df_s.empty: df_s.to_excel(writer, sheet_name=s[:31], index=False)
        
        timestamp = datetime.now().strftime("%d_%m_%Y")
        st.sidebar.download_button("📥 Baixar Backup Geral", output_geral.getvalue(), f"Backup_Geral_{timestamp}.xlsx")

    arquivo_upload = st.sidebar.file_uploader("Importar Backup", type=["xlsx"])
    if arquivo_upload and st.sidebar.button("🚀 Processar Importação"):
        dict_df = pd.read_excel(arquivo_upload, sheet_name=None)
        conn = sqlite3.connect('agendamentos_direcao.db')
        for aba, dados in dict_df.items():
            if 'id' in dados.columns: dados = dados.drop(columns=['id'])
            dados.to_sql('reservas', conn, if_exists='append', index=False)
        conn.close()
        st.rerun()

    with st.sidebar.expander("🗑️ Remover Registros"):
        sala_l = st.selectbox("Sala", todas_as_salas, key="l_s")
        conn = sqlite3.connect('agendamentos_direcao.db')
        df_l = pd.read_sql_query("SELECT id, data, evento FROM reservas WHERE sala=?", conn, params=(sala_l,))
        conn.close()
        if not df_l.empty:
            opc = {f"ID {row['id']} | {row['data']}": row['id'] for _, row in df_l.iterrows()}
            it = st.selectbox("Item", list(opc.keys()))
            if st.button("EXCLUIR"):
                conn = sqlite3.connect('agendamentos_direcao.db')
                conn.execute("DELETE FROM reservas WHERE id=?", (opc[it],))
                conn.commit()
                conn.close()
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Novo Agendamento")
    sala_sel = st.sidebar.selectbox("Espaço", todas_as_salas)
    tipo_ag = st.sidebar.radio("Tipo", ["Pontual", "Por Período"])
    origem_sel = st.sidebar.selectbox("Solicitante", ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"])
    esp_ext = st.sidebar.text_input("Especificar Externo") if origem_sel == "EXTERNO" else ""
    meio_sel = st.sidebar.selectbox("Meio da solicitação", ["E-mail", "SEI", "Presencial", "Outro"])
    sei_n = st.sidebar.text_input("Nº Processo SEI") if meio_sel == "SEI" else ""

    with st.sidebar.form("form_final"):
        if tipo_ag == "Pontual":
            data_ev = st.date_input("Data", format="DD/MM/YYYY")
            d_i, d_f, dias = None, None, []
        else:
            c1, c2 = st.columns(2)
            d_i = c1.date_input("Início", format="DD/MM/YYYY")
            d_f = c2.date_input("Fim", format="DD/MM/YYYY")
            dias = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
        
        h_i = st.time_input("Início", value=time(8, 0), step=1800)
        h_f = st.time_input("Término", value=time(9, 0), step=1800)
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        evento = st.text_area("Finalidade/Evento")
        servidor = st.text_input("Servidor Lançador")
        
        if st.form_submit_button("Confirmar Agendamento"):
            if evento and servidor:
                ori_final = esp_ext if origem_sel == "EXTERNO" else origem_sel
                datas_lista = [data_ev] if tipo_ag == "Pontual" else []
                if tipo_ag == "Por Período":
                    m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                    ind = [m_d[d] for d in dias]
                    curr = d_i
                    while curr <= d_f:
                        if curr.weekday() in ind: datas_lista.append(curr)
                        curr += timedelta(days=1)
                for d in datas_lista:
                    salvar_reserva(sala_sel, d.strftime('%d/%m/%Y'), str(h_i), str(h_f), evento, ori_final, sei_n, st_sel, servidor)
                st.rerun()

# --- 3. COMPONENTES VISUAIS COM NAVEGAÇÃO ---
def calendario_compacto(df_sala):
    # Botões de Navegação
    col_v1, col_v2, col_v3 = st.columns([1, 4, 1])
    
    if col_v1.button("◀", key=f"prev_{st.session_state.mes_ref}"):
        st.session_state.mes_ref -= 1
        if st.session_state.mes_ref == 0:
            st.session_state.mes_ref = 12
            st.session_state.ano_ref -= 1
        st.rerun()
        
    if col_v3.button("▶", key=f"next_{st.session_state.mes_ref}"):
        st.session_state.mes_ref += 1
        if st.session_state.mes_ref == 13:
            st.session_state.mes_ref = 1
            st.session_state.ano_ref += 1
        st.rerun()
    
    mes = st.session_state.mes_ref
    ano = st.session_state.ano_ref
    nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
    
    col_v2.markdown(f"<h3 style='text-align: center; margin:0;'>{nome_mes} / {ano}</h3>", unsafe_allow_html=True)
    
    dias_ocupados = {}
    if not df_sala.empty:
        for _, row in df_sala.iterrows():
            try:
                dt = datetime.strptime(row['data'], '%d/%m/%Y')
                if dt.year == ano and dt.month == mes:
                    if dias_ocupados.get(dt.day) != 'Confirmado': dias_ocupados[dt.day] = row['status']
            except: continue

    html_cal = f"<table style='width:100%; table-layout:fixed; border-collapse:collapse; text-align:center;'><tr>"
    for d in ['D','S','T','Q','Q','S','S']: html_cal += f"<th style='font-size:10px; color:gray;'>{d}</th>"
    html_cal += "</tr>"
    
    for semana in calendar.monthcalendar(ano, mes):
        html_cal += "<tr>"
        for i, dia in enumerate(semana):
            if dia == 0: html_cal += "<td></td>"
            else:
                status = dias_ocupados.get(dia)
                bg = "#3D5AFE" if status == 'Confirmado' else ("#FFAB00" if status == 'Pré-agendado' else ("#fafafa" if i==0 or i==6 else "white"))
                color = "white" if status == 'Confirmado' else ("black" if status == 'Pré-agendado' else "#444")
                html_cal += f"<td style='background-color:{bg}; color:{color}; border:1px solid #f0f0f0; border-radius:4px; font-size:12px; padding:5px;'>{dia}</td>"
        html_cal += "</tr>"
    st.markdown(html_cal + "</table>", unsafe_allow_html=True)

def exibir_tabela(n_sala):
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=? ORDER BY data DESC", conn, params=(n_sala,))
    conn.close()
    
    calendario_compacto(df)
    st.write("---")
    
    if not df.empty:
        # Filtra a tabela para mostrar apenas o mês de referência
        df['dt_temp'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_filtrado = df[(df['dt_temp'].dt.month == st.session_state.mes_ref) & (df['dt_temp'].dt.year == st.session_state.ano_ref)]
        
        if not df_filtrado.empty:
            df_display = df_filtrado[['status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'numero_sei', 'servidor_resp']]
            df_display.columns = ['Status', 'Data', 'Início', 'Fim', 'Descrição', 'Solicitante', 'Nº SEI', 'Lançado por']
            st.dataframe(df_display.style.map(lambda x: f'background-color: {"#d4edda" if x=="Confirmado" else ("#fff3cd" if x=="Pré-agendado" else "#f8d7da")}', subset=['Status']), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum evento para este mês.")
    else: st.info("Sem agendamentos.")

st.subheader("🗓️ Cronograma Principal")
t_a, t_l, t_r = st.tabs(abas_fixas)
with t_a: exibir_tabela("Auditório Rio Amazonas")
with t_l: exibir_tabela("Laboratório de Informática")
with t_r: exibir_tabela("Sala de Reunião")

st.markdown("---")
s_ext = st
