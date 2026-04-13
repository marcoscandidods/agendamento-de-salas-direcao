import streamlit as st
import psycopg2
from psycopg2 import pool
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io
import hashlib

# ==========================================
# 0. CONFIGURAÇÕES E CONSTANTES
# ==========================================
DEPARTAMENTOS = ["DA-FES", "DECON-FES", "DEA-FES", "PROFNIT", "PROFIAP", "PPG-ECO", "PPGADAM", "DIRETORIA", "EXTERNO"]

# ==========================================
# 1. MODEL & CONTROLLER (Lógica e Estabilidade)
# ==========================================

@st.cache_resource
def init_connection_pool():
    """Mantém ligações vivas para evitar lentidão e quedas do banco."""
    try:
        return psycopg2.pool.SimpleConnectionPool(1, 15, st.secrets["DB_URL"])
    except Exception as e:
        st.error(f"Erro ao ligar ao banco: {e}")
        return None

db_pool = init_connection_pool()

def execute_query(query, params=None, fetch=False, commit=False):
    """Executa SQL de forma segura usando o Pool de ligações."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if commit: conn.commit()
            if fetch: return cursor.fetchall()
    except Exception as e:
        st.error(f"Erro na base de dados: {e}")
    finally:
        db_pool.putconn(conn)

def init_db():
    """Cria as tabelas necessárias e garante as colunas de segurança."""
    execute_query('''CREATE TABLE IF NOT EXISTS reservas
                     (id SERIAL PRIMARY KEY, sala TEXT, data TEXT, horario_inicio TEXT, 
                      horario_fim TEXT, evento TEXT, origem TEXT, numero_sei TEXT, 
                      status TEXT, servidor_resp TEXT, email_solicitante TEXT)''', commit=True)
    
    execute_query('''CREATE TABLE IF NOT EXISTS usuarios
                     (id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, 
                      senha TEXT, vinculo TEXT, perfil TEXT DEFAULT 'user')''', commit=True)
    
    execute_query('''CREATE TABLE IF NOT EXISTS lista_salas (nome_sala TEXT PRIMARY KEY)''', commit=True)
    
    salas_pre = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião"] + [f"Sala {i}" for i in range(1, 63)]
    for s in salas_pre:
        execute_query("INSERT INTO lista_salas (nome_sala) VALUES (%s) ON CONFLICT DO NOTHING", (s,), commit=True)

def hash_senha(senha):
    """Criptografa a palavra-passe para segurança."""
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_conflito(sala, data, inicio, fim, id_ignorar=None):
    """Verifica se já existe reserva no horário."""
    query = "SELECT horario_inicio, horario_fim FROM reservas WHERE sala=%s AND data=%s AND status != 'Cancelado'"
    params = [sala, data]
    if id_ignorar:
        query += " AND id != %s"
        params.append(id_ignorar)
    
    agendamentos = execute_query(query, tuple(params), fetch=True)
    if not agendamentos: return False

    format_h = '%H:%M'
    novo_i = datetime.strptime(inicio, format_h).time()
    novo_f = datetime.strptime(fim, format_h).time()

    for ex_i_str, ex_f_str in agendamentos:
        ex_i = datetime.strptime(ex_i_str, format_h).time()
        ex_f = datetime.strptime(ex_f_str, format_h).time()
        if novo_i < ex_f and novo_f > ex_i: return True 
    return False

# ==========================================
# 2. VIEW - CONFIGURAÇÕES E LOGIN MODAL
# ==========================================

st.set_page_config(page_title="Gestão de Espaços - FES", layout="wide")
init_db()

# Inicialização de variáveis de sessão
if 'user' not in st.session_state: st.session_state.user = None
if 'user_dept' not in st.session_state: st.session_state.user_dept = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year
if 'data_mapa_ref' not in st.session_state:
    hoje = datetime.now().date()
    st.session_state.data_mapa_ref = hoje - timedelta(days=hoje.weekday())

abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião", "Salas de Aula"]
salas_de_aula_list = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas[:3] + salas_de_aula_list
lista_h = [(datetime.strptime("07:00", "%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(33)]

@st.dialog("🔑 Acesso ao Sistema")
def login_dialog():
    aba_log, aba_cad = st.tabs(["Entrar", "Criar Conta"])
    with aba_log:
        email_log = st.text_input("E-mail")
        senha_log = st.text_input("Palavra-passe", type="password")
        if st.button("Fazer Login"):
            if "LOGIN_USER" in st.secrets and email_log == st.secrets["LOGIN_USER"] and senha_log == st.secrets["LOGIN_PWD"]:
                st.session_state.user = "Administrador"
                st.session_state.is_admin = True
                st.session_state.user_dept = "DIRETORIA"
                st.rerun()
            else:
                # Selecionando o vínculo para carregar o departamento automaticamente
                res = execute_query("SELECT nome, perfil, vinculo FROM usuarios WHERE email=%s AND senha=%s", 
                                    (email_log, hash_senha(senha_log)), fetch=True)
                if res:
                    st.session_state.user = res[0][0]
                    st.session_state.is_admin = (res[0][1] == 'admin')
                    st.session_state.user_dept = res[0][2]
                    st.rerun()
                else:
                    st.error("E-mail ou palavra-passe incorretos.")

    with aba_cad:
        n_nome = st.text_input("Nome Completo")
        n_email = st.text_input("E-mail Institucional")
        n_senha = st.text_input("Palavra-passe ", type="password")
        vinc = st.selectbox("Departamento / Origem", DEPARTAMENTOS)
        if st.button("Finalizar Registo"):
            with st.spinner("A guardar dados..."):
                execute_query("INSERT INTO usuarios (nome, email, senha, vinculo) VALUES (%s,%s,%s,%s)", 
                             (n_nome, n_email, hash_senha(n_senha), vinc), commit=True)
            st.success("✅ Registo realizado! Agora podes entrar.")

col_t, col_l = st.columns([7, 3])
with col_t:
    st.title("📅 Gestão de Espaços - FES")
with col_l:
    if st.session_state.user:
        st.write(f"Olá, **{st.session_state.user}**")
        st.caption(f"Dep: {st.session_state.user_dept}")
        if st.button("Sair"):
            st.session_state.user = None
            st.session_state.is_admin = False
            st.session_state.user_dept = None
            st.rerun()
    else:
        if st.button("🔑 Entrar / Registar"):
            login_dialog()

# ==========================================
# 3. FUNCIONALIDADES E CALENDÁRIOS
# ==========================================

def consultar_vagos():
    """Busca rápida de salas livres."""
    with st.expander("🔍 Consultar salas disponíveis"):
        c1, c2, c3 = st.columns(3)
        d_busca = c1.date_input("Data desejada", format="DD/MM/YYYY")
        h_i = c2.selectbox("Horário Início", lista_h, key="hib")
        h_f = c3.selectbox("Horário Fim", lista_h, key="hfb")
        if st.button("Verificar Disponibilidade"):
            if lista_h.index(h_f) <= lista_h.index(h_i):
                st.error("Erro: O término deve ser após o início.")
            else:
                q = """SELECT nome_sala FROM lista_salas WHERE nome_sala NOT IN 
                        (SELECT sala FROM reservas WHERE data=%s AND status!='Cancelado' 
                         AND NOT (horario_fim<=%s OR horario_inicio>=%s))"""
                res = execute_query(q, (d_busca.strftime('%d/%m/%Y'), h_i, h_f), fetch=True)
                livres = [r[0] for r in res] if res else []
                if livres: st.success(f"Livres: {', '.join(livres)}")
                else: st.error("Nenhuma sala disponível.")

def calendario_compacto(df_sala, n_sala):
    """Desenho do calendário com indicadores de barras coloridas (Estilo Android)."""
    col1, col2, col3 = st.columns([1, 8, 1])
    if col1.button("◀", key=f"p_{n_sala}"):
        st.session_state.mes_ref -= 1
        if st.session_state.mes_ref == 0: st.session_state.mes_ref = 12; st.session_state.ano_ref -= 1
        st.rerun()
    if col3.button("▶", key=f"n_{n_sala}"):
        st.session_state.mes_ref += 1
        if st.session_state.mes_ref == 13: st.session_state.mes_ref = 1; st.session_state.ano_ref += 1
        st.rerun()
    
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    st.markdown(f"<p style='text-align:center; font-weight:bold; font-size:18px;'>{meses[st.session_state.mes_ref-1]} / {st.session_state.ano_ref}</p>", unsafe_allow_html=True)
    
    dias_ocup = {}
    if not df_sala.empty:
        for _, r in df_sala.iterrows():
            if r['status'] == 'Cancelado': continue
            try:
                dt = datetime.strptime(r['data'], '%d/%m/%Y')
                if dt.year == st.session_state.ano_ref and dt.month == st.session_state.mes_ref:
                    dia = dt.day
                    if dia not in dias_ocup:
                        dias_ocup[dia] = {'m': False, 't': False, 'n': False}
                    
                    # Horários para detectar o turno (Início e Fim vêm da tabela de reservas)
                    h_i = datetime.strptime(r['Início'], '%H:%M').time()
                    h_f = datetime.strptime(r['Fim'], '%H:%M').time()
                    
                    # Manhã: 08:00 - 12:00 | Tarde: 12:00 - 18:00 | Noite: 18:00 - 22:00
                    if h_i < time(12, 0) and h_f > time(8, 0): dias_ocup[dia]['m'] = True
                    if h_i < time(18, 0) and h_f > time(12, 0): dias_ocup[dia]['t'] = True
                    if h_i < time(22, 0) and h_f > time(18, 0): dias_ocup[dia]['n'] = True
            except: continue

    html = """
    <style>
        .cal-table { width:100%; text-align:center; border-collapse: collapse; table-layout: fixed; }
        .cal-table th { color: gray; font-size: 11px; padding-bottom: 5px; }
        .cal-table td { 
            border: 1px solid #333; height: 50px; vertical-align: top; 
            position: relative; padding-top: 5px; font-size: 14px; font-weight: bold;
        }
        .indicator-container {
            position: absolute; bottom: 4px; left: 0; width: 100%;
            display: flex; flex-direction: column; gap: 2px; padding: 0 4px;
        }
        .bar { height: 3.5px; border-radius: 2px; width: 100%; }
        .bar-m { background-color: #3b82f6; } /* Azul - Manhã */
        .bar-t { background-color: #10b981; } /* Verde - Tarde */
        .bar-n { background-color: #f59e0b; } /* Laranja - Noite */
        .weekend { background-color: #1e1e1e; }
    </style>
    <table class='cal-table'><tr>
    """
    for d in ['D','S','T','Q','Q','S','S']: html += f"<th>{d}</th>"
    html += "</tr>"
    for sem in calendar.monthcalendar(st.session_state.ano_ref, st.session_state.mes_ref):
        html += "<tr>"
        for i, dia in enumerate(sem):
            if dia == 0: html += "<td></td>"
            else:
                classe_td = "weekend" if i in [0, 6] else ""
                content = f"<div>{dia}</div>"
                if dia in dias_ocup:
                    bars = "<div class='indicator-container'>"
                    if dias_ocup[dia]['m']: bars += "<div class='bar bar-m'></div>"
                    if dias_ocup[dia]['t']: bars += "<div class='bar bar-t'></div>"
                    if dias_ocup[dia]['n']: bars += "<div class='bar bar-n'></div>"
                    bars += "</div>"
                    content += bars
                html += f"<td class='{classe_td}'>{content}</td>"
        html += "</tr>"
    st.markdown(html + "</table>", unsafe_allow_html=True)
    st.markdown("""
    <div style='display: flex; gap: 15px; font-size: 11px; justify-content: center; margin-top: 10px; color: #aaa;'>
        <div><span style='color: #3b82f6;'>●</span> Manhã </div>
        <div><span style='color: #10b981;'>●</span> Tarde </div>
        <div><span style='color: #f59e0b;'>●</span> Noite </div>
    </div>
    """, unsafe_allow_html=True)

def exibir_tabela(n_sala):
    """Exibe a tabela e a opção de edição para Admin."""
    res = execute_query("SELECT id, status, data, horario_inicio, horario_fim, evento, origem, servidor_resp FROM reservas WHERE sala=%s ORDER BY data DESC", (n_sala,), fetch=True)
    df = pd.DataFrame(res, columns=['ID', 'Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Responsável']) if res else pd.DataFrame()
    
    df_cal = df.rename(columns={'Status':'status', 'Data':'data'}) if not df.empty else df
    calendario_compacto(df_cal, n_sala)
    st.markdown("---")
    
    if not df.empty:
        st.dataframe(df.style.map(lambda x: f'background-color: {"#16a34a" if x=="Confirmado" else ("#ca8a04" if x in ["Pré-agendado", "Em Análise"] else "#dc2626")}; color: white; font-weight: bold', subset=['Status']), use_container_width=True, hide_index=True)
        
        if st.session_state.is_admin:
            with st.expander("📝 Editar Agendamento (Admin)"):
                id_ed = st.selectbox("Selecione o ID para editar:", df['ID'], key=f"sel_{n_sala}")
                row = df[df['ID'] == id_ed].iloc[0]
                c1, c2 = st.columns(2)
                novo_st = c1.selectbox("Novo Status", ["Confirmado", "Em Análise", "Cancelado"], index=["Confirmado", "Em Análise", "Cancelado"].index(row['Status']), key=f"st_{id_ed}")
                nova_desc = c2.text_input("Nova Descrição", value=row['Descrição'], key=f"desc_{id_ed}")
                if st.button("Confirmar Alteração", key=f"btn_{id_ed}"):
                    execute_query("UPDATE reservas SET status=%s, evento=%s WHERE id=%s", (novo_st, nova_desc, id_ed), commit=True)
                    st.success("Atualizado!"); st.rerun()

def resumo_semanal_navegavel():
    """Visão Geral de todas as salas de aula."""
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("◀ Semana Anterior"): st.session_state.data_mapa_ref -= timedelta(days=7); st.rerun()
    if c3.button("Próxima Semana ▶"): st.session_state.data_mapa_ref += timedelta(days=7); st.rerun()
    seg = st.session_state.data_mapa_ref
    st.markdown(f"<div style='text-align:center; background:#1e1e1e; padding:10px; border-radius:10px;'>Semana: {seg.strftime('%d/%m')} a {(seg+timedelta(days=5)).strftime('%d/%m/%Y')}</div>", unsafe_allow_html=True)
    res = execute_query("SELECT id, sala, data, horario_inicio, horario_fim, evento, status FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", fetch=True)
    df = pd.DataFrame(res, columns=['id','sala','data','hi','hf', 'evento', 'status']) if res else pd.DataFrame()
    d_s = [(seg + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(6)]
    for s in salas_de_aula_list:
        cols = st.columns([1.5, 2, 2, 2, 2, 2, 2])
        cols[0].markdown(f"<div style='font-size:11px; font-weight:bold;'>{s}</div>", unsafe_allow_html=True)
        for i, ds in enumerate(d_s):
            with cols[i+1]:
                if not df.empty:
                    evs = df[(df['sala'] == s) & (df['data'] == ds)]
                    for _, r in evs.iterrows():
                        cor = "#1e40af" if r['status'] == "Confirmado" else "#D97706"
                        st.markdown(f"<div style='font-size:8px; padding:2px; border-radius:3px; background:{cor}; color:white;'>{r['hi']}-{r['hf']}</div>", unsafe_allow_html=True)

def formulario_agendamento():
    """Formulário lateral fixo com Origem Automática baseada no departamento do perfil."""
    if st.session_state.user:
        with st.sidebar:
            st.header("📝 Novo Agendamento")
            with st.form("form_unificado"):
                sala_f = st.selectbox("Escolha o Espaço", todas_as_salas)
                d_f = st.date_input("Data", format="DD/MM/YYYY")
                hi_f = st.selectbox("Início", lista_h, index=2)
                hf_f = st.selectbox("Fim", lista_h, index=4)
                
                # Preenchimento automático da origem baseado no departamento do utilizador
                if st.session_state.is_admin:
                    # Admin pode escolher qualquer departamento se necessário
                    origem_f = st.selectbox("Origem (Departamento)", DEPARTAMENTOS, 
                                          index=DEPARTAMENTOS.index(st.session_state.user_dept) if st.session_state.user_dept in DEPARTAMENTOS else 0)
                else:
                    # Utilizador comum usa o seu departamento fixo
                    origem_f = st.session_state.user_dept
                    st.info(f"Origem automática: **{origem_f}**")
                
                evento_f = "Aulas Regulares"
                if st.form_submit_button("Salvar Agendamento"):
                    d_str = d_f.strftime('%d/%m/%Y')
                    if lista_h.index(hf_f) <= lista_h.index(hi_f): st.error("Horário inválido!")
                    elif verificar_conflito(sala_f, d_str, hi_f, hf_f): st.error("Conflito de horário!")
                    else:
                        st_b = "Confirmado" if st.session_state.is_admin else "Em Análise"
                        execute_query("INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, origem, status, email_solicitante) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (sala_f, d_str, hi_f, hf_f, evento_f, origem_f, st_b, st.session_state.user), commit=True)
                        st.success("Sucesso!"); st.rerun()

# ==========================================
# 4. EXECUÇÃO FINAL
# ==========================================

consultar_vagos()
formulario_agendamento()
t_aud, t_lab, t_reu, t_salas = st.tabs(abas_fixas)
with t_aud: exibir_tabela("Auditório Rio Amazonas")
with t_lab: exibir_tabela("Laboratório de Informática")
with t_reu: exibir_tabela("Sala de Reunião")
with t_salas:
    st.subheader("🏫 Gestão de Salas de Aula")
    sala_foco = st.selectbox("Escolha a Sala:", salas_de_aula_list, index=0)
    exibir_tabela(sala_foco)
    st.markdown("---")
    st.markdown("""
        <style>
            .resumo-label {
                font-size: 22px !important;
                font-weight: bold !important;
                color: #FFFFFF;
                margin-bottom: -10px;
            }
        </style>
        <p class="resumo-label">🗓️ Visão Geral das Salas (Mapa Semanal)</p>
    """, unsafe_allow_html=True)
    
    if st.toggle("Ativar Resumo Semanal (Mapa Geral)"): 
        resumo_semanal_navegavel()

# SEU TEXTO DE ISENÇÃO
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #6b7280; font-size: 13px; line-height: 1.6;'>
    <p>🚀 <b>Desenvolvido voluntariamente por Marcos Candido</b></p>
    <p>Este software é uma ferramenta académica experimental de apoio administrativo, desenvolvida como parte de um 
    <b>Projeto de Extensão do Curso de Engenharia de Software</b> para fins estritamente académicos e sem fins lucrativos.</p>
</div>
""", unsafe_allow_html=True)
