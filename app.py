import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
# Nova biblioteca para o calendário ficar sempre aberto
from streamlit_calendar import calendar

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
        esp_ext = st.sidebar.text_input("Especificar Externo (Quem?)")
    
    meio_opc = ["E-mail", "SEI", "Presencial", "Outro"]
    meio_sel = st.sidebar.selectbox("Meio da solicitação", meio_opc)
    sei_n = ""
    if meio_sel == "SEI":
        sei_n = st.sidebar.text_input("Nº Processo SEI")

    with st.sidebar.form("form_final"):
        if tipo_ag == "Pontual":
            data_ev = st.date_input("Data do Evento", format="DD/MM/YYYY")
            d_i, d_f, dias = None, None, []
        else:
            c1, c2 = st.columns(2)
            d_i = c1.date_input("Início", format="DD/MM/YYYY")
            d_f = c2.date_input("Fim", format="DD/MM/YYYY")
            dias = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
            data_ev = None

        h_i = st.time_input("Início", step=1800)
        h_f = st.time_input("Término", step=1800)
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        
        conf_c = True
        if st_sel == "Cancelado":
            conf_c = st.checkbox("Confirmar cancelamento")
        
        evento = st.text_area("Finalidade/Evento")
        servidor = st.text_input("Servidor Lançador")
        
        if st.form_submit_button("Confirmar Agendamento"):
            if st_sel == "Cancelado" and not conf_c:
                st.error("Confirme o cancelamento.")
            elif evento and servidor:
                ori_final = esp_ext if origem_sel == "EXTERNO" else origem_sel
                datas_lista = []
                if tipo_ag == "Pontual":
                    datas_lista = [data_ev]
                else:
                    m = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                    ind = [m[d] for d in dias]
                    curr = d_i
                    while curr <= d_f:
                        if curr.weekday() in ind:
                            datas_lista.append(curr)
                        curr += timedelta(days=1)
                
                for d in datas_lista:
                    salvar_reserva(sala_sel, d.strftime('%d/%m/%Y'), str(h_i), str(h_f), evento, ori_final, sei_n, st_sel, servidor)
                st.rerun()
            else:
                st.warning("Preencha os campos obrigatórios.")

# --- 3. VISUALIZAÇÃO ---
def exibir_tabela(n_sala):
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=? ORDER BY data DESC", conn, params=(n_sala,))
    conn.close()

    # --- CALENDÁRIO VISÍVEL NO TOPO (FULL CALENDAR) ---
    st.write(f"📅 **Calendário de Ocupação: {n_sala}**")
    
    calendar_events = []
    if not df.empty:
        for _, row in df.iterrows():
            if row['status'] != 'Cancelado':
                # Converte data para formato ISO para o calendário
                data_iso = datetime.strptime(row['data'], '%d/%m/%Y').strftime('%Y-%m-%d')
                calendar_events.append({
                    "title": f"{row['horario_inicio']} - {row['evento']}",
                    "start": data_iso,
                    "end": data_iso,
                    "color": "#3D5AFE" if row['status'] == 'Confirmado' else "#FFAB00"
                })

    calendar_options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek"
        },
        "initialView": "dayGridMonth",
        "locale": "pt-br",
    }
    
    calendar(events=calendar_events, options=calendar_options, key=f"full_cal_{n_sala}")

    st.markdown("---")

    if not df.empty:
        df_display = df.copy()
        df_display = df_display[['status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'numero_sei', 'servidor_resp']]
        df_display.columns = ['Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Nº SEI', 'Lançado por']
        
        cores = {'Confirmado': '#d4edda', 'Pré-agendado': '#fff3cd', 'Cancelado': '#f8d7da'}
        st.dataframe(df_display.style.map(lambda x: f'background-color: {cores.get(x, "#ffffff")}; color: black', subset=['Status']), 
                     use_container_width=True, hide_index=True)
        
        if logado:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='xlsxwriter') as wr:
                df_display.to_excel(wr, index=False)
            st.download_button(f"📥 Excel - {n_sala}", out.getvalue(), f"{n_sala}.xlsx", key=f"d_{n_sala}")
    else:
        st.info(f"Sem agendamentos registrados para {n_sala}.")

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
