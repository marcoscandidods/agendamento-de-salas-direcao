import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io

# --- 1. CONFIGURAÇÃO E BANCO DE DADOS ---
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

# Estados para o calendário mensal
if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year

# ESTADO PARA O MAPA SEMANAL (Navegação)
if 'data_mapa_ref' not in st.session_state:
    hoje = datetime.now().date()
    # Ajusta para a segunda-feira da semana atual
    st.session_state.data_mapa_ref = hoje - timedelta(days=hoje.weekday())

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
    col_v1, col_v2, col_v3 = st.columns([1, 8, 1])
    with col_v1:
        if st.button("◀", key=f"p_{n_sala}", use_container_width=True):
            st.session_state.mes_ref -= 1
            if st.session_state.mes_ref == 0: st.session_state.mes_ref = 12; st.session_state.ano_ref -= 1
            st.rerun()
    with col_v2:
        mes, ano = st.session_state.mes_ref, st.session_state.ano_ref
        nome_mes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][mes-1]
        st.markdown(f"<p style='text-align:center; font-weight:bold; font-size:18px; margin:0;'>{nome_mes} / {ano}</p>", unsafe_allow_html=True)
    with col_v3:
        if st.button("▶", key=f"n_{n_sala}", use_container_width=True):
            st.session_state.mes_ref += 1
            if st.session_state.mes_ref == 13: st.session_state.mes_ref = 1; st.session_state.ano_ref += 1
            st.rerun()
    
    dias_ocupados = {}
    if not df_sala.empty:
        for _, row in df_sala.iterrows():
            try:
                dt = datetime.strptime(row['data'], '%d/%m/%Y')
                if dt.year == ano and dt.month == mes:
                    if dias_ocupados.get(dt.day) != 'Confirmado': dias_ocupados[dt.day] = row['status']
            except: continue

    html_cal = """
    <style>
        .cal-table { width:100%; text-align:center; border-collapse: collapse; table-layout: fixed; margin-top:10px;}
        .cal-table th { font-size:12px; color:gray; padding: 5px; }
        .cal-table td { border: 1px solid #444 !important; height: 35px; font-size: 13px; font-weight: bold; vertical-align: middle; }
    </style>
    """
    html_cal += "<table class='cal-table'><tr>"
    for d in ['D','S','T','Q','Q','S','S']: html_cal += f"<th>{d}</th>"
    html_cal += "</tr>"
    for semana in calendar.monthcalendar(ano, mes):
        html_cal += "<tr>"
        for i, dia in enumerate(semana):
            if dia == 0: html_cal += "<td style='border: 1px solid #333 !important;'></td>"
            else:
                status = dias_ocupados.get(dia)
                if status == 'Confirmado': bg, color = "#2563EB", "white"
                elif status == 'Pré-agendado': bg, color = "#D97706", "white"
                else:
                    bg = "#1e1e1e" if (i == 0 or i == 6) else "transparent"
                    color = "#888" if (i == 0 or i == 6) else "#ccc"
                html_cal += f"<td style='background-color:{bg}; color:{color};'>{dia}</td>"
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
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#16a34a" if x=="Confirmado" else ("#ca8a04" if x=="Pré-agendado" else "#dc2626")}; color: white; font-weight: bold', subset=['Status']), 
                         use_container_width=True, hide_index=True)
            if logado:
                with st.expander("✏️ Editar Agendamento"):
                    id_edit = st.selectbox("ID", disp['ID'], key=f"sel_{n_sala}")
                    row_edit = df[df['id'] == id_edit].iloc[0]
                    c1, c2 = st.columns(2)
                    new_ev = c1.text_input("Finalidade", value=row_edit['evento'], key=f"ev_{id_edit}")
                    new_st = c2.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"], 
                                             index=["Confirmado", "Pré-agendado", "Cancelado"].index(row_edit['status']), key=f"st_{id_edit}")
                    if st.button("Salvar Alterações", key=f"btn_edit_{id_edit}", use_container_width=True):
                        atualizar_reserva(id_edit, new_ev, row_edit['origem'], row_edit['numero_sei'], new_st, row_edit['servidor_resp'], 
                                          row_edit['horario_inicio'], row_edit['horario_fim'], row_edit['data'])
                        st.rerun()
                with st.popover("🗑️ Excluir"):
                    confirmar = st.checkbox("Confirmar exclusão definitiva", key=f"check_del_{id_edit}")
                    if st.button("CONFIRMAR", key=f"btn_del_{id_edit}", disabled=not confirmar, type="primary"):
                        conn = sqlite3.connect('agendamentos_direcao.db'); conn.execute("DELETE FROM reservas WHERE id=?", (id_edit,)); conn.commit(); conn.close()
                        st.rerun()

# --- 4. ABA RESUMO (MAPA DE OCUPAÇÃO SEMANAL NAVEGÁVEL) ---
def resumo_semanal_navegavel():
    # --- CONTROLES DE NAVEGAÇÃO ---
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Semana Anterior", use_container_width=True):
            st.session_state.data_mapa_ref -= timedelta(days=7)
            st.rerun()
    with c3:
        if st.button("Próxima Semana ▶", use_container_width=True):
            st.session_state.data_mapa_ref += timedelta(days=7)
            st.rerun()
            
    # Datas da semana selecionada
    segunda = st.session_state.data_mapa_ref
    sabado = segunda + timedelta(days=5)
    
    with c2:
        st.markdown(f"""
            <div style='text-align:center; padding:5px; background-color:#1e1e1e; border-radius:10px; border:1px solid #333;'>
                <h4 style='margin:0; color:#2563EB;'>Semana: {segunda.strftime('%d/%m')} a {sabado.strftime('%d/%m/%Y')}</h4>
            </div>
        """, unsafe_allow_html=True)

    st.write("")

    # --- BUSCA E FILTRO DE DADOS ---
    conn = sqlite3.connect('agendamentos_direcao.db')
    df = pd.read_sql_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", conn)
    conn.close()

    # CSS para os Cartões
    st.markdown("""
        <style>
        .resumo-container { display: flex; flex-direction: column; gap: 12px; width: 100%; }
        .resumo-row { display: grid; grid-template-columns: 120px 1fr; border-bottom: 1px solid #333; padding: 10px 0; align-items: start; }
        .resumo-sala { font-weight: bold; color: #fff; font-size: 15px; background: #262730; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #444; }
        .resumo-dias { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
        .dia-col { min-width: 0; }
        .dia-header { font-size: 10px; color: #888; text-transform: uppercase; margin-bottom: 6px; text-align: center; font-weight: bold; }
        .card-container { display: flex; flex-direction: column; gap: 5px; }
        .event-card { 
            font-size: 10px; padding: 6px; border-radius: 6px; color: white; line-height: 1.2;
            word-wrap: break-word; font-weight: 600; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
        }
        .vazio { color: #333; font-size: 14px; text-align: center; }
        
        @media (max-width: 768px) {
            .resumo-row { grid-template-columns: 1fr; }
            .resumo-dias { grid-template-columns: 1fr 1fr; } 
            .resumo-sala { margin-bottom: 10px; background: #2563EB; }
        }
        </style>
    """, unsafe_allow_html=True)

    dias_semana_nomes = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    
    def get_color(origem):
        if "DA-FES" in origem: return "#1e40af"
        if "DECON" in origem: return "#166534"
        if "DEA" in origem: return "#9a3412"
        if "DIRETORIA" in origem: return "#6b21a8"
        return "#4b5563"

    html = "<div class='resumo-container'>"
    
    # Geramos a lista de datas da semana atual para o filtro
    datas_semana = [(segunda + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(6)]

    for s in salas_de_aula_list:
        df_sala = df[df['sala'] == s].copy()
        
        html += f"<div class='resumo-row'><div class='resumo-sala'>{s}</div>"
        html += "<div class='resumo-dias'>"
        
        for idx, d_nome in enumerate(dias_semana_nomes):
            data_alvo = datas_semana[idx]
            html += f"<div class='dia-col'><div class='dia-header'>{d_nome} ({data_alvo[:5]})</div><div class='card-container'>"
            
            if not df_sala.empty:
                # Filtra exatamente pela data daquela coluna na semana selecionada
                eventos = df_sala[df_sala['data'] == data_alvo].sort_values(by="horario_inicio")
                if not eventos.empty:
                    for _, r in eventos.drop_duplicates(subset=['horario_inicio', 'horario_fim', 'origem']).iterrows():
                        cor = get_color(r['origem'])
                        html += f"<div class='event-card' style='background-color:{cor};'>{r['horario_inicio']}-{r['horario_fim']}<br>{r['origem']}</div>"
                else: html += "<div class='vazio'>-</div>"
            else: html += "<div class='vazio'>-</div>"
            
            html += "</div></div>"
        html += "</div></div>"
        
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    
    st.markdown("---")
    st.write("#### 🔍 Consultar Detalhes Específicos")
    s_det = st.selectbox("Escolha uma sala para gerenciar:", ["Selecione..."] + salas_de_aula_list)
    if s_det != "Selecione...": exibir_tabela(s_det)

# --- EXECUÇÃO ---
t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semanal_navegavel()

# --- RODAPÉ ---
st.markdown("<br><br><p style='text-align: center; color: #6b7280; font-size: 14px;'>🚀 Desenvolvido por <b>Marcos Candido</b> - Projeto de Extensão</p>", unsafe_allow_html=True)
