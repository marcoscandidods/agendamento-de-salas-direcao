import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io

# --- 1. CONFIGURAÇÃO E CONEXÃO COM BANCO EXTERNO (NEON/POSTGRES) ---
def get_connection():
    """Cria uma conexão com o banco de dados PostgreSQL no Neon usando Secrets."""
    return psycopg2.connect(st.secrets["DB_URL"])

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reservas
                 (id SERIAL PRIMARY KEY,
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
    c.close()
    conn.close()

def verificar_conflito(sala, data, inicio, fim, id_ignorar=None):
    """Verifica se existe sobreposição de horários na mesma sala e data."""
    conn = get_connection()
    c = conn.cursor()
    query = "SELECT id, horario_inicio, horario_fim FROM reservas WHERE sala=%s AND data=%s AND status != 'Cancelado'"
    params = [sala, data]
    
    if id_ignorar:
        query += " AND id != %s"
        params.append(id_ignorar)
        
    c.execute(query, params)
    agendamentos = c.fetchall()
    c.close()
    conn.close()

    format_h = '%H:%M'
    novo_i = datetime.strptime(inicio, format_h).time()
    novo_f = datetime.strptime(fim, format_h).time()

    for ag_id, ex_i_str, ex_f_str in agendamentos:
        ex_i = datetime.strptime(ex_i_str, format_h).time()
        ex_f = datetime.strptime(ex_f_str, format_h).time()

        if novo_i < ex_f and novo_f > ex_i:
            return True 
    return False 

def atualizar_reserva(id_reserva, evento, origem, sei, status, servidor, h_i, h_f, data):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""UPDATE reservas SET evento=%s, origem=%s, numero_sei=%s, status=%s, servidor_resp=%s, 
                 horario_inicio=%s, horario_fim=%s, data=%s WHERE id=%s""", 
              (evento, origem, sei, status, servidor, h_i, h_f, data, id_reserva))
    conn.commit()
    c.close()
    conn.close()

def salvar_reserva(sala, data, inicio, fim, evento, origem, sei, status, servidor):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, origem, numero_sei, status, servidor_resp) 
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
              (sala, data, inicio, fim, evento, origem, sei, status, servidor))
    conn.commit()
    c.close()
    conn.close()
    return True

# --- FUNÇÃO AUXILIAR PARA LISTA DE HORÁRIOS ---
def gerar_lista_horarios():
    horarios = []
    start = datetime.strptime("07:00", "%H:%M")
    end = datetime.strptime("23:00", "%H:%M")
    while start <= end:
        horarios.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return horarios

# --- 2. INTERFACE E SESSÃO ---
st.set_page_config(page_title="Gestão de Espaços - Direção", layout="wide")
init_db()

st.title("📅 Gestão de Espaços - Direção")

if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year

if 'data_mapa_ref' not in st.session_state:
    hoje = datetime.now().date()
    st.session_state.data_mapa_ref = hoje - timedelta(days=hoje.weekday())

if 'logado' not in st.session_state: st.session_state.logado = False

# --- ÁREA DE LOGIN PROTEGIDA ---
with st.sidebar.form("login_form"):
    st.header("🔐 Área Restrita")
    u_input = st.text_input("Usuário")
    s_input = st.text_input("Senha", type="password")
    
    if st.form_submit_button("Acessar Sistema"):
        if "LOGIN_USER" in st.secrets and "LOGIN_PWD" in st.secrets:
            if u_input == st.secrets["LOGIN_USER"] and s_input == st.secrets["LOGIN_PWD"]:
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        else:
            st.error("Erro crítico: As chaves de login não foram configuradas nos Secrets.")

logado = st.session_state.logado
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião", "Salas de Aula"]
salas_de_aula_list = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas[:3] + salas_de_aula_list
lista_h = gerar_lista_horarios()

if logado:
    st.sidebar.success("Sessão Ativa")
    st.sidebar.warning("⚠️ **AVISO LGPD**: Dados sensíveis não devem constar aqui.")
    
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    
    st.sidebar.markdown("---")
    conn = get_connection()
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
        
        # Ajuste: Selectbox para horários
        h_i = st.selectbox("Horário Início", lista_h, index=lista_h.index("08:00"))
        h_f = st.selectbox("Horário Término", lista_h, index=lista_h.index("09:00"))
        
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
            
            conflitos = []
            for d in datas:
                d_str = d.strftime('%d/%m/%Y')
                if verificar_conflito(sala_sel_side, d_str, h_i, h_f):
                    conflitos.append(d_str)
                else:
                    salvar_reserva(sala_sel_side, d_str, h_i, h_f, evento, ori_f, sei_n, st_sel, servidor)
            
            if conflitos:
                st.error(f"Erro: Conflito nas datas: {', '.join(conflitos)}")
            else:
                st.success("Salvo com sucesso!")
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

    html_cal = """<style>.cal-table { width:100%; text-align:center; border-collapse: collapse; table-layout: fixed; margin-top:10px;}.cal-table th { font-size:12px; color:gray; padding: 5px; }.cal-table td { border: 1px solid #444 !important; height: 35px; font-size: 13px; font-weight: bold; vertical-align: middle; }</style>"""
    html_cal += "<table class='cal-table'><tr>"
    for d in ['D','S','T','Q','Q','S','S']: html_cal += f"<th>{d}</th>"
    html_cal += "</tr>"
    for semana in calendar.monthcalendar(ano, mes):
        html_cal += "<tr>"
        for i, dia in enumerate(semana):
            if dia == 0: html_cal += "<td style='border: 1px solid #333 !important;'></td>"
            else:
                status = dias_ocupados.get(dia)
                bg = "#2563EB" if status == 'Confirmado' else ("#D97706" if status == 'Pré-agendado' else ("#1e1e1e" if i==0 or i==6 else "transparent"))
                color = "white" if status in ['Confirmado', 'Pré-agendado'] else ("#888" if i==0 or i==6 else "#ccc")
                html_cal += f"<td style='background-color:{bg}; color:{color};'>{dia}</td>"
        html_cal += "</tr>"
    st.markdown(html_cal + "</table>", unsafe_allow_html=True)

def exibir_tabela(n_sala, mostrar_cal=True):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM reservas WHERE sala=%s ORDER BY data DESC", conn, params=(n_sala,))
    conn.close()
    if mostrar_cal: calendario_compacto(df, n_sala)
    st.write("---")
    if not df.empty:
        df['dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_f = df[(df['dt'].dt.month == st.session_state.mes_ref) & (df['dt'].dt.year == st.session_state.ano_ref)]
        if not df_f.empty:
            disp = df_f[['id', 'status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'servidor_resp']]
            disp.columns = ['ID', 'Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Lançador']
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#16a34a" if x=="Confirmado" else ("#ca8a04" if x=="Pré-agendado" else "#dc2626")}; color: white; font-weight: bold', subset=['Status']), use_container_width=True, hide_index=True)
            if logado:
                with st.expander("✏️ Editar Agendamento"):
                    id_edit = st.selectbox("Selecione o ID", disp['ID'], key=f"sel_{n_sala}")
                    row_edit = df[df['id'] == id_edit].iloc[0]
                    c1, c2 = st.columns(2)
                    new_ev = c1.text_input("Finalidade", value=row_edit['evento'], key=f"ev_{id_edit}")
                    new_st = c2.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"], index=["Confirmado", "Pré-agendado", "Cancelado"].index(row_edit['status']), key=f"st_{id_edit}")
                    
                    # Ajuste: Selectbox na edição
                    h_i_e = st.selectbox("Novo Início", lista_h, index=lista_h.index(row_edit['horario_inicio']), key=f"hi_{id_edit}")
                    h_f_e = st.selectbox("Novo Término", lista_h, index=lista_h.index(row_edit['horario_fim']), key=f"hf_{id_edit}")

                    if st.button("Salvar Alterações", key=f"btn_edit_{id_edit}", use_container_width=True):
                        if verificar_conflito(row_edit['sala'], row_edit['data'], h_i_e, h_f_e, id_ignorar=id_edit):
                            st.error("Conflito de horário!")
                        else:
                            atualizar_reserva(id_edit, new_ev, row_edit['origem'], row_edit['numero_sei'], new_st, row_edit['servidor_resp'], h_i_e, h_f_e, row_edit['data'])
                            st.rerun()
                with st.popover("🗑️ Excluir"):
                    confirmar = st.checkbox("Confirmar exclusão definitiva", key=f"check_del_{id_edit}")
                    if st.button("CONFIRMAR EXCLUSÃO", key=f"btn_del_{id_edit}", disabled=not confirmar, type="primary"):
                        conn = get_connection(); c = conn.cursor()
                        c.execute("DELETE FROM reservas WHERE id=%s", (id_edit,))
                        conn.commit(); c.close(); conn.close()
                        st.rerun()

# --- 4. ABA RESUMO SEMANAL NAVEGÁVEL ---
def resumo_semanal_navegavel():
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Semana Anterior", use_container_width=True):
            st.session_state.data_mapa_ref -= timedelta(days=7); st.rerun()
    with c3:
        if st.button("Próxima Semana ▶", use_container_width=True):
            st.session_state.data_mapa_ref += timedelta(days=7); st.rerun()
            
    segunda = st.session_state.data_mapa_ref
    sabado = segunda + timedelta(days=5)
    st.markdown(f"<div style='text-align:center; padding:10px; background:#1e1e1e; border-radius:10px; border:1px solid #333;'><h4 style='margin:0; color:#2563EB;'>Semana: {segunda.strftime('%d/%m')} a {sabado.strftime('%d/%m/%Y')}</h4></div>", unsafe_allow_html=True)

    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", conn)
    conn.close()

    st.markdown("""<style>.resumo-container { display: flex; flex-direction: column; gap: 12px; width: 100%; }.resumo-row { display: grid; grid-template-columns: 120px 1fr; border-bottom: 1px solid #333; padding: 10px 0; align-items: start; }.resumo-sala { font-weight: bold; color: #fff; font-size: 15px; background: #262730; padding: 10px; border-radius: 8px; text-align: center; border: 1px solid #444; }.resumo-dias { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }.dia-col { min-width: 0; }.dia-header { font-size: 10px; color: #888; text-transform: uppercase; margin-bottom: 6px; text-align: center; font-weight: bold; }.card-container { display: flex; flex-direction: column; gap: 5px; }.event-card { font-size: 10px; padding: 6px; border-radius: 6px; color: white; line-height: 1.2; word-wrap: break-word; font-weight: 600; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); }.vazio { color: #333; font-size: 14px; text-align: center; } @media (max-width: 768px) { .resumo-row { grid-template-columns: 1fr; } .resumo-dias { grid-template-columns: 1fr 1fr; } .resumo-sala { margin-bottom: 10px; background: #2563EB; } }</style>""", unsafe_allow_html=True)

    dias_semana_nomes = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    def get_color(origem):
        if "DA-FES" in origem: return "#1e40af"
        if "DECON" in origem: return "#166534"
        if "DEA" in origem: return "#9a3412"
        if "DIRETORIA" in origem: return "#6b21a8"
        return "#4b5563"

    datas_semana = [(segunda + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(6)]
    html = "<div class='resumo-container'>"
    for s in salas_de_aula_list:
        df_sala = df[df['sala'] == s].copy()
        html += f"<div class='resumo-row'><div class='resumo-sala'>{s}</div><div class='resumo-dias'>"
        for idx, d_nome in enumerate(dias_semana_nomes):
            data_alvo = datas_semana[idx]
            html += f"<div class='dia-col'><div class='dia-header'>{d_nome} ({data_alvo[:5]})</div><div class='card-container'>"
            if not df_sala.empty:
                eventos = df_sala[df_sala['data'] == data_alvo].sort_values(by="horario_inicio")
                if not eventos.empty:
                    for _, r in eventos.drop_duplicates(subset=['horario_inicio', 'horario_fim', 'origem']).iterrows():
                        html += f"<div class='event-card' style='background-color:{get_color(r['origem'])};'>{r['horario_inicio']}-{r['horario_fim']}<br>{r['origem']}</div>"
                else: html += "<div class='vazio'>-</div>"
            else: html += "<div class='vazio'>-</div>"
            html += "</div></div>"
        html += "</div></div>"
    st.markdown(html + "</div>", unsafe_allow_html=True)
    
    st.markdown("---")
    s_det = st.selectbox("Consultar Sala específica:", ["Selecione..."] + salas_de_aula_list)
    if s_det != "Selecione...": exibir_tabela(s_det)

# --- EXECUÇÃO ---
t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semanal_navegavel()

# --- RODAPÉ COM ISENÇÃO DE RESPONSABILIDADE ---
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b7280; font-size: 13px; line-height: 1.6;'>
    <p>🚀 <b>Desenvolvido voluntariamente por Marcos Candido</b></p>
    <p>Este software é uma ferramenta acadêmica experimental de apoio administrativo, desenvolvida como parte de um 
    <b>Projeto de Extensão do Curso de Engenharia de Software</b> para fins estritamente acadêmicos e sem fins lucrativos.</p>
    <p style='font-style: italic;'>
        O sistema é fornecido "como está", sem garantias de suporte técnico ou disponibilidade contínua, 
        operando integralmente em serviços de nuvem gratuitos (GitHub, Streamlit e Neon). 
        O desenvolvedor não se responsabiliza por limitações dessas plataformas ou pela integridade permanente dos dados.
    </p>
</div>
""", unsafe_allow_html=True)
