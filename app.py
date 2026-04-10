import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
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
                  solicitante TEXT,
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

def salvar_reserva(sala, data, inicio, fim, evento, solicitante, origem, sei, status, servidor):
    if status != "Cancelado" and verificar_conflito(sala, data, inicio, fim):
        return False
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("""INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, solicitante, origem, numero_sei, status, servidor_resp) 
                 VALUES (?,?,?,?,?,?,?,?,?,?)""", (sala, data, inicio, fim, evento, solicitante, origem, sei, status, servidor))
    conn.commit()
    conn.close()
    return True

def deletar_registro(id_registro):
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("DELETE FROM reservas WHERE id=?", (id_registro,))
    conn.commit()
    conn.close()

# --- 2. INTERFACE E SEGURANÇA ---
st.set_page_config(page_title="Sistema de Agendamento - Direção", layout="wide")
init_db()

st.title("📅 Gestão de Espaços - Direção")

# Configuração de Acesso na Sidebar
st.sidebar.header("🔐 Área Restrita")
usuario = st.sidebar.text_input("Usuário", key="user_input")
senha = st.sidebar.text_input("Senha", type="password", key="pass_input")

USER_CORRETO = "diretoriafes"
SENHA_CORRETA = "secretariafes2021/2"
logado = (usuario == USER_CORRETO and senha == SENHA_CORRETA)

# Definição das Salas
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião"]
salas_de_aula = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas + salas_de_aula

if logado:
    st.sidebar.success("Logado: Diretoria")
    
    # --- MÓDULO DE BACKUP ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛡️ Segurança e Backup")
    if st.sidebar.button("✅ Marcar Backup Semanal como FEITO"):
        st.balloons()
        st.sidebar.success(f"Backup confirmado em: {datetime.now().strftime('%d/%m/%Y')}")

    # --- MÓDULO DE EXCLUSÃO (LIMPEZA) ---
    st.sidebar.markdown("---")
    with st.sidebar.expander("🗑️ Gerenciar/Remover Registros"):
        sala_limpeza = st.selectbox("Sala para limpeza", todas_as_salas)
        conn = sqlite3.connect('agendamentos_direcao.db')
        df_limp = pd.read_sql_query("SELECT id, data, evento FROM reservas WHERE sala=?", conn, params=(sala_limpeza,))
        conn.close()
        
        if not df_limp.empty:
            opcoes_excluir = {f"ID {row['id']} | {row['data']} | {row['evento'][:20]}...": row['id'] for _, row in df_limp.iterrows()}
            item_sel = st.selectbox("Selecione o registro para APAGAR", list(opcoes_excluir.keys()))
            if st.button("❗ EXCLUIR PERMANENTEMENTE"):
                deletar_registro(opcoes_excluir[item_sel])
                st.sidebar.warning("Registro removido.")
                st.rerun()
        else:
            st.write("Nenhum registro encontrado.")

    st.warning("**⚠️ AVISO LGPD:** As informações são públicas. Use o SEI/E-mail para dados sensíveis.")
    
    st.sidebar.markdown("---")
    tipo_agendamento = st.sidebar.radio("Tipo de Agendamento", ["Pontual", "Por Período (Recorrente)"])
    
    # --- FORMULÁRIO DE AGENDAMENTO ---
    with st.sidebar.form("form_reserva"):
        sala_sel = st.selectbox("Selecione o Espaço", todas_as_salas)
        if tipo_agendamento == "Pontual":
            data_evento = st.date_input("Data do Evento", format="DD/MM/YYYY")
        else:
            col_a, col_b = st.columns(2)
            d_ini = col_a.date_input("Início")
            d_fim = col_b.date_input("Fim")
            dias_sem = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])

        h_ini = st.time_input("Início", step=1800)
        h_fim = st.time_input("Término", step=1800)
        status_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        
        conf_cancel = True
        if status_sel == "Cancelado":
            st.error("⚠️ REGISTRO DE CANCELAMENTO")
            conf_cancel = st.checkbox("Confirmo o cancelamento desta reserva.")
        
        evento = st.text_area("Finalidade/Evento")
        solicitante = st.text_input("Solicitante")
        servidor_resp = st.text_input("Servidor Lançador")
        
        # Departamento de Origem (Apenas os Departamentos)
        origem_opc = ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"]
        origem_sel = st.selectbox("Departamento de Origem", origem_opc)

        # Meio ou forma da solicitação (Substituindo o campo Externo antigo)
        meio_solicitacao = st.selectbox("Meio ou forma da solicitação", ["SEI", "E-mail", "Presencial", "Outro"])
        
        # Campo condicional: Só aparece se for SEI
        sei_num = ""
        if meio_solicitacao == "SEI":
            sei_num = st.text_input("Nº Processo SEI")
            
        btn_salvar = st.form_submit_button("Confirmar Agendamento")

    if btn_salvar:
        if status_sel == "Cancelado" and not conf_cancel:
            st.sidebar.error("Confirme o cancelamento.")
        elif evento and solicitante and servidor_resp:
            # Lógica de Datas
            datas = [data_evento] if tipo_agendamento == "Pontual" else []
            if tipo_agendamento != "Pontual":
                mapa = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                indices = [mapa[d] for d in dias_sem]
                curr = d_ini
                while curr <= d_fim:
                    if curr.weekday() in indices: datas.append(curr)
                    curr += timedelta(days=1)

            sucessos = 0
            for d in datas:
                if salvar_reserva(sala_sel, d.strftime('%d/%m/%Y'), str(h_ini), str(h_fim), evento, solicitante, origem_sel, sei_num, status_sel, servidor_resp):
                    sucessos += 1
            st.sidebar.success(f"{sucessos} registro(s) salvo(s)!")
            st.rerun()
        else:
            st.sidebar.warning("⚠️ Preencha os campos obrigatórios.")
else:
    st.sidebar.info("Acesso restrito. Faça login para gerenciar.")

# --- 3. VISUALIZAÇÃO PÚBLICA ---
def exibir_tabela(nome_sala):
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=? ORDER BY data DESC, horario_inicio ASC", conn, params=(nome_sala,))
    conn.close()
    
    if not df.empty:
        df_display = df.copy()
        df_display.columns = ['ID', 'Sala', 'Data', 'Início', 'Fim', 'Descrição', 'Solicitante', 'Origem', 'Nº SEI', 'Status', 'Lançado por']
        df_display = df_display.drop(columns=['Sala'])
        
        cores = {'Confirmado': '#d4edda', 'Pré-agendado': '#fff3cd', 'Cancelado': '#f8d7da'}
        st.dataframe(df_display.style.map(lambda x: f'background-color: {cores.get(x, "#ffffff")}; color: black', subset=['Status']), 
                     use_container_width=True, hide_index=True)
        
        if logado:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_display.to_excel(writer, index=False)
            st.download_button(label=f"📥 Baixar Excel - {nome_sala}", data=output.getvalue(), file_name=f"{nome_sala}.xlsx", key=f"btn_{nome_sala}")
    else:
        st.info(f"Nenhum agendamento para {nome_sala}.")

st.subheader("🗓️ Cronograma Principal")
tab_audit, tab_lab, tab_reuniao = st.tabs(abas_fixas)

with tab_audit: exibir_tabela("Auditório Rio Amazonas")
with tab_lab: exibir_tabela("Laboratório de Informática")
with tab_reuniao: exibir_tabela("Sala de Reunião")

st.markdown("---")
st.subheader("🔍 Salas de Aula")
sala_extra = st.selectbox("Selecione uma sala de aula:", ["Selecione uma sala..."] + salas_de_aula)
if sala_extra != "Selecione uma sala...":
    exibir_tabela(sala_extra)

st.markdown("---")
st.caption("🚀 Desenvolvido por **Marcos Candido** - Projeto de Extensão do Curso de Engenharia de Software")
