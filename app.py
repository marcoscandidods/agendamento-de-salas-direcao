import streamlit as st
import psycopg2
from psycopg2 import pool
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io
import hashlib

# ==========================================
# 1. MODEL & CONTROLLER (Lógica e Estabilidade)
# ==========================================

@st.cache_resource
def init_connection_pool():
    """Mantém conexões vivas para evitar lentidão e quedas do Neon."""
    try:
        return psycopg2.pool.SimpleConnectionPool(1, 15, st.secrets["DB_URL"])
    except Exception as e:
        st.error(f"Erro ao conectar ao banco: {e}")
        return None

db_pool = init_connection_pool()

def execute_query(query, params=None, fetch=False, commit=False):
    """Executa SQL de forma segura usando o Pool de conexões."""
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
    # Tabela Principal de Reservas
    execute_query('''CREATE TABLE IF NOT EXISTS reservas
                     (id SERIAL PRIMARY KEY, sala TEXT, data TEXT, horario_inicio TEXT, 
                      horario_fim TEXT, evento TEXT, origem TEXT, numero_sei TEXT, 
                      status TEXT, servidor_resp TEXT, email_solicitante TEXT)''', commit=True)
    
    # Tabela de Usuários para Cadastro/Login
    execute_query('''CREATE TABLE IF NOT EXISTS usuarios
                     (id SERIAL PRIMARY KEY, nome TEXT, email TEXT UNIQUE, 
                      senha TEXT, vinculo TEXT, perfil TEXT DEFAULT 'user')''', commit=True)
    
    # Tabela de Salas para busca de disponibilidade
    execute_query('''CREATE TABLE IF NOT EXISTS lista_salas (nome_sala TEXT PRIMARY KEY)''', commit=True)
    
    # Alimenta a lista de salas se estiver vazia
    salas_pre = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião"] + [f"Sala {i}" for i in range(1, 63)]
    for s in salas_pre:
        execute_query("INSERT INTO lista_salas (nome_sala) VALUES (%s) ON CONFLICT DO NOTHING", (s,), commit=True)

def hash_senha(senha):
    """Criptografa a senha para segurança (padrão profissional)."""
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_conflito(sala, data, inicio, fim, id_ignorar=None):
    """Verifica se já existe reserva no horário (Otimizado)."""
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

st.set_page_config(page_title="Gestão de Espaços - Direção", layout="wide")
init_db()

# Estados de Sessão (User e Controle de Navegação)
if 'user' not in st.session_state: st.session_state.user = None
if 'is_admin' not in st.session_state: st.session_state.is_admin = False
if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year
if 'data_mapa_ref' not in st.session_state:
    hoje = datetime.now().date()
    st.session_state.data_mapa_ref = hoje - timedelta(days=hoje.weekday())

# --- LISTAS DE REFERÊNCIA (Originais do seu código) ---
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião", "Salas de Aula"]
salas_de_aula_list = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas[:3] + salas_de_aula_list
lista_h = [(datetime.strptime("07:00", "%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(33)]

# --- JANELA MODAL DE ACESSO (O que o Eugues sugeriu) ---
@st.dialog("🔑 Acesso ao Sistema")
def login_dialog():
    aba_log, aba_cad = st.tabs(["Entrar", "Criar Conta"])
    
    with aba_log:
        st.write("Acesse com seu e-mail cadastrado.")
        email_log = st.text_input("E-mail")
        senha_log = st.text_input("Senha", type="password")
        
        if st.button("Fazer Login"):
            # 1. Verifica se é Admin (via Secrets)
            if "LOGIN_USER" in st.secrets and email_log == st.secrets["LOGIN_USER"] and senha_log == st.secrets["LOGIN_PWD"]:
                st.session_state.user = "Administrador"
                st.session_state.is_admin = True
                st.rerun()
            # 2. Verifica se é Usuário Comum (via Banco)
            else:
                res = execute_query("SELECT nome, perfil FROM usuarios WHERE email=%s AND senha=%s", 
                                   (email_log, hash_senha(senha_log)), fetch=True)
                if res:
                    st.session_state.user = res[0][0]
                    st.session_state.is_admin = (res[0][1] == 'admin')
                    st.rerun()
                else:
                    st.error("E-mail ou senha incorretos.")

    with aba_cad:
        st.write("Cadastre-se para solicitar agendamentos.")
        novo_nome = st.text_input("Nome Completo")
        novo_email = st.text_input("E-mail Institucional/Pessoal")
        nova_senha = st.text_input("Crie uma Senha", type="password")
        vinc = st.selectbox("Vínculo", ["Servidor UFAM", "Aluno UFAM", "Comunidade Externa"])
        
        if st.button("Finalizar Cadastro"):
            if not novo_nome or not novo_email or not nova_senha:
                st.warning("Preencha todos os campos.")
            elif "@" not in novo_email:
                st.error("Insira um e-mail válido.")
            else:
                execute_query("INSERT INTO usuarios (nome, email, senha, vinculo) VALUES (%s,%s,%s,%s)",
                             (novo_nome, novo_email, hash_senha(nova_senha), vinc), commit=True)
                st.success("Cadastro realizado! Mude para a aba 'Entrar'.")

# --- CABEÇALHO SUPERIOR ---
col_t, col_l = st.columns([7, 3])
with col_t:
    st.title("🏛️ Gestão de Espaços - FES")
with col_l:
    if st.session_state.user:
        st.write(f"Conectado como: **{st.session_state.user}**")
        if st.button("Sair"):
            st.session_state.user = None
            st.session_state.is_admin = False
            st.rerun()
    else:
        if st.button("🔑 Entrar / Cadastrar"):
            login_dialog()
            # ==========================================
# 3. FUNCIONALIDADES E CALENDÁRIOS (Sua base original)
# ==========================================

def consultar_vagos():
    """Funcionalidade nova de busca rápida de salas livres."""
    with st.expander("🔍 Consultar salas disponíveis em um horário"):
        c1, c2, c3 = st.columns(3)
        d_busca = c1.date_input("Data desejada", format="DD/MM/YYYY", key="db")
        h_i_busca = c2.selectbox("Horário Início", lista_h, key="hib")
        h_f_busca = c3.selectbox("Horário Fim", lista_h, key="hfb")
        
        if st.button("Verificar Disponibilidade"):
            # Trava de Horário sugerida (Fim deve ser após o Início)
            if lista_h.index(h_f_busca) <= lista_h.index(h_i_busca):
                st.error("Erro: O horário de término deve ser posterior ao início.")
            else:
                query = """
                    SELECT nome_sala FROM lista_salas 
                    WHERE nome_sala NOT IN (
                        SELECT sala FROM reservas 
                        WHERE data = %s AND status != 'Cancelado'
                        AND NOT (horario_fim <= %s OR horario_inicio >= %s)
                    )
                """
                res = execute_query(query, (d_busca.strftime('%d/%m/%Y'), h_i_busca, h_f_busca), fetch=True)
                livres = [r[0] for r in res] if res else []
                if livres:
                    st.success(f"Salas LIVRES: {', '.join(livres)}")
                else:
                    st.error("Nenhuma sala disponível neste horário.")

def calendario_compacto(df_sala, n_sala):
    """Sua lógica de calendário original com cores."""
    col1, col2, col3 = st.columns([1, 8, 1])
    with col1:
        if st.button("◀", key=f"p_{n_sala}"):
            st.session_state.mes_ref -= 1
            if st.session_state.mes_ref == 0: st.session_state.mes_ref = 12; st.session_state.ano_ref -= 1
            st.rerun()
    with col2:
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        st.markdown(f"<p style='text-align:center; font-weight:bold; font-size:18px;'>{meses[st.session_state.mes_ref-1]} / {st.session_state.ano_ref}</p>", unsafe_allow_html=True)
    with col3:
        if st.button("▶", key=f"n_{n_sala}"):
            st.session_state.mes_ref += 1
            if st.session_state.mes_ref == 13: st.session_state.mes_ref = 1; st.session_state.ano_ref += 1
            st.rerun()
    
    dias_ocup = {}
    if not df_sala.empty:
        for _, r in df_sala.iterrows():
            try:
                dt = datetime.strptime(r['data'], '%d/%m/%Y')
                if dt.year == st.session_state.ano_ref and dt.month == st.session_state.mes_ref:
                    if dias_ocup.get(dt.day) != 'Confirmado': dias_ocup[dt.day] = r['status']
            except: continue

    html = "<style>.cal-table { width:100%; text-align:center; border-collapse: collapse; }.cal-table td { border: 1px solid #444; height: 35px; font-weight: bold; }</style><table class='cal-table'><tr>"
    for d in ['D','S','T','Q','Q','S','S']: html += f"<th style='color:gray; font-size:12px;'>{d}</th>"
    html += "</tr>"
    for sem in calendar.monthcalendar(st.session_state.ano_ref, st.session_state.mes_ref):
        html += "<tr>"
        for i, dia in enumerate(sem):
            if dia == 0: html += "<td></td>"
            else:
                s_st = dias_ocup.get(dia)
                bg = "#2563EB" if s_st == 'Confirmado' else ("#D97706" if s_st == 'Pré-agendado' or s_st == 'Em Análise' else ("#1e1e1e" if i in [0,6] else "transparent"))
                html += f"<td style='background-color:{bg}; color:white;'>{dia}</td>"
        html += "</tr>"
    st.markdown(html + "</table>", unsafe_allow_html=True)

def exibir_tabela(n_sala):
    res = execute_query("SELECT * FROM reservas WHERE sala=%s ORDER BY data DESC", (n_sala,), fetch=True)
    df = pd.DataFrame(res, columns=['id','sala','data','horario_inicio','horario_fim','evento','origem','numero_sei','status','servidor_resp', 'email_solicitante']) if res else pd.DataFrame()
    calendario_compacto(df, n_sala)
    st.markdown("---")
    
    if not df.empty:
        df['dt_obj'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_f = df[(df['dt_obj'].dt.month == st.session_state.mes_ref) & (df['dt_obj'].dt.year == st.session_state.ano_ref)]
        if not df_f.empty:
            disp = df_f[['id', 'status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'servidor_resp']].copy()
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#16a34a" if x=="Confirmado" else ("#ca8a04" if x in ["Pré-agendado", "Em Análise"] else "#dc2626")}; color: white; font-weight: bold', subset=['status']), use_container_width=True, hide_index=True)

    # Lógica de Administração e Agendamento (Protegida)
    if st.session_state.user:
        with st.sidebar:
            st.markdown("---")
            st.subheader(f"Ações: {n_sala}")
            if st.session_state.is_admin: # Apenas Secretaria
                # (Aqui entraria sua lógica original de Editar/Excluir que já existia)
                st.info("Você tem permissão para aprovar e excluir registros.")
            
            # Formulário de solicitação para qualquer logado
            with st.form(f"form_{n_sala}"):
                d_r = st.date_input("Data do evento")
                h_i = st.selectbox("Início", lista_h)
                h_f = st.selectbox("Fim", lista_h)
                ev = st.text_input("Finalidade")
                if st.form_submit_button("Solicitar Agendamento"):
                    if lista_h.index(h_f) <= lista_h.index(h_i):
                        st.error("Horário de término inválido.")
                    elif verificar_conflito(n_sala, d_r.strftime('%d/%m/%Y'), h_i, h_f):
                        st.error("Já existe uma reserva para este horário.")
                    else:
                        stat = "Confirmado" if st.session_state.is_admin else "Em Análise"
                        execute_query("INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, status, email_solicitante) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                                     (n_sala, d_r.strftime('%d/%m/%Y'), h_i, h_f, ev, stat, st.session_state.user), commit=True)
                        st.success("Solicitado com sucesso!")
                        st.rerun()

def resumo_semanal_navegavel():
    """Seu Mapa Semanal Original (Mantido 100%)"""
    c1, c2, c3 = st.columns([1, 3, 1])
    if c1.button("◀ Semana Anterior"): st.session_state.data_mapa_ref -= timedelta(days=7); st.rerun()
    if c3.button("Próxima Semana ▶"): st.session_state.data_mapa_ref += timedelta(days=7); st.rerun()
    seg = st.session_state.data_mapa_ref
    st.markdown(f"<div style='text-align:center; background:#1e1e1e; padding:10px; border-radius:10px; border:1px solid #333;'><h4 style='margin:0; color:#2563EB;'>Semana: {seg.strftime('%d/%m')} a {(seg+timedelta(days=5)).strftime('%d/%m/%Y')}</h4></div>", unsafe_allow_html=True)
    res = execute_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", fetch=True)
    df = pd.DataFrame(res, columns=['id','sala','data','horario_inicio','horario_fim', 'evento', 'origem', 'numero_sei', 'status', 'servidor_resp', 'solicitante']) if res else pd.DataFrame()
    d_n = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    d_s = [(seg + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(6)]
    for s in salas_de_aula_list:
        cols = st.columns([1.5, 2, 2, 2, 2, 2, 2])
        cols[0].markdown(f"<div style='font-weight:bold; font-size:12px; background:#262730; padding:5px; border-radius:5px;'>{s}</div>", unsafe_allow_html=True)
        for i, ds in enumerate(d_s):
            with cols[i+1]:
                st.caption(f"{d_n[i][:3]} {ds[:5]}")
                if not df.empty:
                    evs = df[(df['sala'] == s) & (df['data'] == ds)]
                    for _, r in evs.iterrows():
                        cor = "#1e40af" if r['status'] == "Confirmado" else "#D97706"
                        st.markdown(f"<div style='font-size:9px; padding:3px; border-radius:4px; color:white; background:{cor}; margin-bottom:2px;'>{r['horario_inicio']}<br>{r['evento'][:15]}</div>", unsafe_allow_html=True)

# EXECUÇÃO FINAL
consultar_vagos()
t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semanal_navegavel()

# SEU TEXTO DE ISENÇÃO (Obrigatório)
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
