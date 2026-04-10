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

def atualizar_reserva(id_reserva, evento, origem, sei, status, servidor, h_i, h_f, data):
    conn = sqlite3.connect('agendamentos_direcao.db')
    c = conn.cursor()
    c.execute("""UPDATE reservas SET evento=?, origem=?, numero_sei=?, status=?, servidor_resp=?, 
                 horario_inicio=?, horario_fim=?, data=? WHERE id=?""", 
              (evento, origem, sei, status, servidor, h_i, h_f, data, id_reserva))
    conn.commit()
    conn.close()

def salvar_reserva(sala, data, inicio, fim, evento, origem, sei, status, servidor):
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

st.title("📅 Gestão de Espaços - Direção")

if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year
if 'logado' not in st.session_state: st.session_state.logado = False

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
    
    # Backup
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
        st.sidebar.download_button("📥 Backup Geral", output_geral.getvalue(), f"Backup_{datetime.now().strftime('%d_%m_%Y')}.xlsx")

    # Cadastro
    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Novo Agendamento")
    sala_sel_side = st.sidebar.selectbox("Espaço", todas_as_salas, key="side_sala")
    tipo_ag = st.sidebar.radio("Tipo", ["Pontual", "Por Período"])
    
    with st.sidebar.form("form_novo"):
        origem_sel = st.selectbox("Solicitante", ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"])
        esp_ext = st.text_input("Se Externo, quem?")
        meio_sel = st.selectbox("Meio", ["E-mail", "SEI", "Presencial", "Outro"])
        sei_n = st.text_input("Nº SEI")
        
        if tipo_ag == "Pontual": data_ev = st.date_input("Data", format="DD/MM/YYYY")
        else:
            d_i = st.date_input("Início", format="DD/MM/YYYY")
            d_f = st.date_input("Fim", format="DD/MM/YYYY")
            dias = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
        
        h_i = st.time_input("Início", value=time(8, 0), step=1800)
        h_f = st.time_input("Término", value=time(9, 0), step=1800)
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        evento = st.text_area("Finalidade")
        servidor = st.text_input("Lançador")
        
        if st.form_submit_button("Salvar"):
            ori_f = esp_ext if origem_sel == "EXTERNO" else origem_sel
            datas = [data_ev] if tipo_ag == "Pontual" else []
            if tipo_ag == "Por Período":
                m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
                ind = [m_d[d] for d in dias]
                curr = d_i
                while curr <= d_f:
                    if curr.weekday() in ind: datas.append(curr)
                    curr += timedelta(days=1)
            for d in datas:
                salvar_reserva(sala_sel_side, d.strftime('%d/%m/%Y'), str(h_i)[:5], str(h_f)[:5], evento, ori_f, sei_n, st_sel, servidor)
            st.rerun()

# --- 3. COMPONENTES VISUAIS ---
def calendario_compacto(df_sala, n_sala):
    col_v1, col_v2, col_v3 = st.columns([1, 4, 1])
    if col_v1.button("◀", key=f"p_{n_sala}"):
        st.session_state.mes_ref -= 1
        if st.session_state.mes_ref == 0: st.session_state.mes_ref = 12; st.session_state.ano_ref -= 1
        st.rerun()
    if col_v3.button("▶", key=f"n_{n_sala}"):
        st.session_state.mes_ref += 1
        if st.session_state.mes_ref == 13: st.session_state.mes_ref = 1; st.session_state.ano_ref += 1
        st.rerun()
    
    mes, ano = st.session_state.mes_ref, st.session_state.ano_ref
    nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
    col_v2.markdown(f"<p style='text-align:center; font-weight:bold; margin:0;'>{nome_mes} / {ano}</p>", unsafe_allow_html=True)
    
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
    if mostrar_cal: calendario_compacto(df, n_sala)
    st.write("---")
    if not df.empty:
        df['dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_f = df[(df['dt'].dt.month == st.session_state.mes_ref) & (df['dt'].dt.year == st.session_state.ano_ref)]
        if not df_f.empty:
            disp = df_f[['id', 'status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'servidor_resp']]
            disp.columns = ['ID', 'Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Lançador']
            # REMOÇÃO DE LINKS: Através do column_config
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#d4edda" if x=="Confirmado" else ("#fff3cd" if x=="Pré-agendado" else "#f8d7da")}', subset=['Status']), 
                         use_container_width=True, hide_index=True)
            
            # MODAL DE EDIÇÃO
            if logado:
                with st.expander("✏️ Editar ou Excluir Agendamento"):
                    id_edit = st.selectbox("Selecione o ID para editar", disp['ID'], key=f"sel_{n_sala}")
                    row_edit = df[df['id'] == id_edit].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    new_ev = col1.text_input("Nova Finalidade", value=row_edit['evento'], key=f"ev_{id_edit}")
                    new_st = col2.selectbox("Novo Status", ["Confirmado", "Pré-agendado", "Cancelado"], 
                                            index=["Confirmado", "Pré-agendado", "Cancelado"].index(row_edit['status']), key=f"st_{id_edit}")
                    
                    if st.button("Salvar Alterações", key=f"btn_edit_{id_edit}"):
                        atualizar_reserva(id_edit, new_ev, row_edit['origem'], row_edit['numero_sei'], new_st, row_edit['servidor_resp'], 
                                          row_edit['horario_inicio'], row_edit['horario_fim'], row_edit['data'])
                        st.success("Atualizado!")
                        st.rerun()
                    
                    if st.button("❗ EXCLUIR DEFINITIVAMENTE", key=f"btn_del_{id_edit}"):
                        conn = sqlite3.connect('agendamentos_direcao.db')
                        conn.execute("DELETE FROM reservas WHERE id=?", (id_edit,))
                        conn.commit()
                        conn.close()
                        st.rerun()

# --- 4. ABA RESUMO SEMESTRAL ---
def resumo_semestral():
    st.write("### 🏛️ Mapa de Ocupação Semanal - Salas de Aula")
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", conn)
    conn.close()

    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    resumo_data = []
    for s in salas_de_aula_list:
        linha = {"Sala": s}
        for d_nome in dias_semana:
            m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
            df_sala_dia = df[df['sala'] == s].copy()
            if not df_sala_dia.empty:
                df_sala_dia['dw'] = pd.to_datetime(df_sala_dia['data'], format='%d/%m/%Y').dt.weekday
                eventos = df_sala_dia[df_sala_dia['dw'] == m_d[d_nome]]
                if not eventos.empty:
                    txt = " | ".join([f"{r['horario_inicio']}-{r['horario_fim']} ({r['origem']})" for _, r in eventos.drop_duplicates(subset=['horario_inicio', 'horario_fim', 'origem']).iterrows()])
                    linha[d_nome] = txt
                else: linha[d_nome] = "-"
            else: linha[d_nome] = "-"
        resumo_data.append(linha)

    df_resumo = pd.DataFrame(resumo_data)

    # CORES FORTES E NÍTIDAS
    def colorir_celula(val):
        if "DA-FES" in val: return 'background-color: #1565C0; color: white; font-weight: bold' # Azul Forte
        if "DECON" in val: return 'background-color: #2E7D32; color: white; font-weight: bold' # Verde Forte
        if "DEA" in val: return 'background-color: #EF6C00; color: white; font-weight: bold' # Laranja Forte
        if "DIRETORIA" in val: return 'background-color: #6A1B9A; color: white; font-weight: bold' # Roxo Forte
        return 'color: #757575'

    st.dataframe(df_resumo.style.map(colorir_celula), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.write("#### 🔍 Detalhes por Sala")
    s_detalhe = st.selectbox("Escolha uma sala:", ["Selecione..."] + salas_de_aula_list, key="sel_aula")
    if s_detalhe != "Selecione...": exibir_tabela(s_detalhe)

# --- EXECUÇÃO ---
t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semestral()

st.caption("🚀 Desenvolvido por **Marcos Candido** - Projeto de Extensão do Curso de Engenharia de Software")
