import streamlit as st
import psycopg2
from psycopg2 import pool
import pandas as pd
from datetime import datetime, timedelta, time
import calendar
import io

# ==========================================
# 1. MODEL & CONTROLLER (O "Cérebro" do App)
# ==========================================

@st.cache_resource
def init_connection_pool():
    """Resolve a instabilidade: mantém conexões prontas (Connection Pool)."""
    try:
        return psycopg2.pool.SimpleConnectionPool(1, 15, st.secrets["DB_URL"])
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

db_pool = init_connection_pool()

def execute_query(query, params=None, fetch=False, commit=False):
    """Função mestre para operações seguras no PostgreSQL."""
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if commit: conn.commit()
            if fetch: return cursor.fetchall()
    except Exception as e:
        st.error(f"Erro no banco: {e}")
    finally:
        db_pool.putconn(conn)

def init_db():
    execute_query('''CREATE TABLE IF NOT EXISTS reservas
                     (id SERIAL PRIMARY KEY, sala TEXT, data TEXT, horario_inicio TEXT, 
                      horario_fim TEXT, evento TEXT, origem TEXT, numero_sei TEXT, 
                      status TEXT, servidor_resp TEXT)''', commit=True)

def verificar_conflito(sala, data, inicio, fim, id_ignorar=None):
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
# 2. VIEW - CONFIGURAÇÕES E ESTILO
# ==========================================

st.set_page_config(page_title="Gestão de Espaços - Direção", layout="wide")
init_db()

if 'mes_ref' not in st.session_state: st.session_state.mes_ref = datetime.now().month
if 'ano_ref' not in st.session_state: st.session_state.ano_ref = datetime.now().year
if 'data_mapa_ref' not in st.session_state:
    hoje = datetime.now().date()
    st.session_state.data_mapa_ref = hoje - timedelta(days=hoje.weekday())
if 'logado' not in st.session_state: st.session_state.logado = False

# --- LISTAS DE REFERÊNCIA ---
abas_fixas = ["Auditório Rio Amazonas", "Laboratório de Informática", "Sala de Reunião", "Salas de Aula"]
salas_de_aula_list = ["Sala 1", "Sala 2", "Sala 4"] + [f"Sala {i}" for i in range(34, 62)]
todas_as_salas = abas_fixas[:3] + salas_de_aula_list
lista_h = [(datetime.strptime("07:00", "%H:%M") + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(33)]

# --- ÁREA DE LOGIN ---
with st.sidebar.form("login_form"):
    st.header("🔐 Área Restrita")
    u_input = st.text_input("Usuário")
    s_input = st.text_input("Senha", type="password")
    if st.form_submit_button("Acessar Sistema"):
        if "LOGIN_USER" in st.secrets and "LOGIN_PWD" in st.secrets:
            if u_input == st.secrets["LOGIN_USER"] and s_input == st.secrets["LOGIN_PWD"]:
                st.session_state.logado = True
                st.rerun()
            else: st.error("Dados inválidos.")
        else: st.error("Erro: Verifique os Secrets.")

logado = st.session_state.logado

# ==========================================
# 3. INTERFACE LOGADA (FUNCIONALIDADES)
# ==========================================

if logado:
    st.sidebar.success("Sessão Ativa")
    st.sidebar.warning("⚠️ **AVISO LGPD**: Dados sensíveis não devem constar aqui.")
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
    
    # --- DOWNLOAD BACKUP ---
    st.sidebar.markdown("---")
    res_total = execute_query("SELECT * FROM reservas", fetch=True)
    if res_total:
        df_total = pd.DataFrame(res_total, columns=['id','sala','data','horario_inicio','horario_fim','evento','origem','numero_sei','status','servidor_resp'])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for s in todas_as_salas:
                df_s = df_total[df_total['sala'] == s]
                if not df_s.empty: df_s.to_excel(writer, sheet_name=s[:31], index=False)
        st.sidebar.download_button("📥 Backup Geral Excel", output.getvalue(), f"Backup_{datetime.now().strftime('%d_%m_%Y')}.xlsx")

    # --- FORMULÁRIO NOVO AGENDAMENTO ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📝 Novo Agendamento")
    sala_side = st.sidebar.selectbox("Espaço", todas_as_salas)
    tipo_ag = st.sidebar.radio("Tipo", ["Pontual", "Por Período"])
    
    with st.sidebar.form("form_novo"):
        origem_sel = st.selectbox("Solicitante", ["DA-FES", "DECON-FES", "DEA-FES", "DIRETORIA", "EXTERNO"])
        esp_ext = st.text_input("Se Externo, quem?")
        sei_n = st.text_input("Nº SEI")
        if tipo_ag == "Pontual": datas_alvo = [st.date_input("Data", format="DD/MM/YYYY")]
        else:
            d_i = st.date_input("Início", format="DD/MM/YYYY")
            d_f = st.date_input("Fim", format="DD/MM/YYYY")
            dias_w = st.multiselect("Dias", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
            datas_alvo = []
            m_d = {"Segunda":0, "Terça":1, "Quarta":2, "Quinta":3, "Sexta":4, "Sábado":5}
            curr = d_i
            while curr <= d_f:
                if any(curr.weekday() == m_d[d] for d in dias_w): datas_alvo.append(curr)
                curr += timedelta(days=1)
        
        h_i = st.selectbox("Início", lista_h, index=lista_h.index("08:00"))
        h_f = st.selectbox("Fim", lista_h, index=lista_h.index("09:00"))
        st_sel = st.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"])
        evento = st.text_area("Finalidade")
        servidor = st.text_input("Lançador")
        
        if st.form_submit_button("Salvar"):
            ori_f = esp_ext if origem_sel == "EXTERNO" else origem_sel
            conflitos = []
            for d in datas_alvo:
                d_s = d.strftime('%d/%m/%Y')
                if verificar_conflito(sala_side, d_s, h_i, h_f): conflitos.append(d_s)
                else:
                    execute_query("INSERT INTO reservas (sala, data, horario_inicio, horario_fim, evento, origem, numero_sei, status, servidor_resp) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
                                 (sala_side, d_s, h_i, h_f, evento, ori_f, sei_n, st_sel, servidor), commit=True)
            if conflitos: st.error(f"Conflitos: {', '.join(conflitos)}")
            else: st.success("Salvo!"); st.rerun()

# ==========================================
# 4. COMPONENTES VISUAIS (CALENDÁRIO E TABELA)
# ==========================================

def calendario_compacto(df_sala, n_sala):
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
    for d in ['D','S','T','Q','Q','S','S']: html += f"<th style='color:gray;'>{d}</th>"
    html += "</tr>"
    for sem in calendar.monthcalendar(st.session_state.ano_ref, st.session_state.mes_ref):
        html += "<tr>"
        for i, dia in enumerate(sem):
            if dia == 0: html += "<td></td>"
            else:
                stt = dias_ocup.get(dia)
                bg = "#2563EB" if stt == 'Confirmado' else ("#D97706" if stt == 'Pré-agendado' else ("#1e1e1e" if i in [0,6] else "transparent"))
                html += f"<td style='background-color:{bg}; color:white;'>{dia}</td>"
        html += "</tr>"
    st.markdown(html + "</table>", unsafe_allow_html=True)

def exibir_tabela(n_sala):
    res = execute_query("SELECT * FROM reservas WHERE sala=%s ORDER BY data DESC", (n_sala,), fetch=True)
    df = pd.DataFrame(res, columns=['id','sala','data','horario_inicio','horario_fim','evento','origem','numero_sei','status','servidor_resp']) if res else pd.DataFrame()
    calendario_compacto(df, n_sala)
    st.markdown("---")
    if not df.empty:
        df['dt_obj'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        df_f = df[(df['dt_obj'].dt.month == st.session_state.mes_ref) & (df['dt_obj'].dt.year == st.session_state.ano_ref)]
        if not df_f.empty:
            disp = df_f[['id', 'status', 'data', 'horario_inicio', 'horario_fim', 'evento', 'origem', 'servidor_resp']].copy()
            disp.columns = ['ID', 'Status', 'Data', 'Início', 'Fim', 'Descrição', 'Origem', 'Lançador']
            st.dataframe(disp.style.map(lambda x: f'background-color: {"#16a34a" if x=="Confirmado" else ("#ca8a04" if x=="Pré-agendado" else "#dc2626")}; color: white; font-weight: bold', subset=['Status']), use_container_width=True, hide_index=True)
            if logado:
                with st.expander("✏️ Editar/Excluir"):
                    id_ed = st.selectbox("ID", disp['ID'], key=f"ed_{n_sala}")
                    r_ed = df[df['id'] == id_ed].iloc[0]
                    c1, c2 = st.columns(2)
                    new_ev = c1.text_input("Finalidade", value=r_ed['evento'], key=f"ev_{id_ed}")
                    new_st = c2.selectbox("Status", ["Confirmado", "Pré-agendado", "Cancelado"], index=["Confirmado", "Pré-agendado", "Cancelado"].index(r_ed['status']), key=f"st_{id_ed}")
                    new_hi = st.selectbox("Início", lista_h, index=lista_h.index(r_ed['horario_inicio']), key=f"hi_{id_ed}")
                    new_hf = st.selectbox("Fim", lista_h, index=lista_h.index(r_ed['horario_fim']), key=f"hf_{id_ed}")
                    if st.button("Salvar Alterações", key=f"btn_{id_ed}"):
                        if verificar_conflito(n_sala, r_ed['data'], new_hi, new_hf, id_ignorar=id_ed): st.error("Conflito!")
                        else:
                            execute_query("UPDATE reservas SET evento=%s, status=%s, horario_inicio=%s, horario_fim=%s WHERE id=%s", (new_ev, new_st, new_hi, new_hf, id_ed), commit=True)
                            st.rerun()
                    if st.button("🗑️ EXCLUIR REGISTRO", key=f"del_{id_ed}", type="primary"):
                        execute_query("DELETE FROM reservas WHERE id=%s", (id_ed,), commit=True)
                        st.rerun()

# ==========================================
# 5. MAPA SEMANAL (SALAS DE AULA)
# ==========================================

def resumo_semanal_navegavel():
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀ Semana Anterior"): st.session_state.data_mapa_ref -= timedelta(days=7); st.rerun()
    with c3:
        if st.button("Próxima Semana ▶"): st.session_state.data_mapa_ref += timedelta(days=7); st.rerun()
            
    seg = st.session_state.data_mapa_ref
    st.markdown(f"<div style='text-align:center; background:#1e1e1e; padding:10px; border-radius:10px; border:1px solid #333;'><h4 style='margin:0; color:#2563EB;'>Semana: {seg.strftime('%d/%m')} a {(seg+timedelta(days=5)).strftime('%d/%m/%Y')}</h4></div>", unsafe_allow_html=True)

    res = execute_query("SELECT * FROM reservas WHERE status != 'Cancelado' AND sala LIKE 'Sala%'", fetch=True)
    df = pd.DataFrame(res, columns=['id','sala','data','horario_inicio','horario_fim', 'evento', 'origem', 'numero_sei', 'status', 'servidor_resp']) if res else pd.DataFrame()

    st.markdown("""<style>.resumo-row { display: grid; grid-template-columns: 100px repeat(6, 1fr); gap: 5px; border-bottom: 1px solid #333; padding: 5px 0; }.resumo-sala { font-weight: bold; font-size: 12px; background: #262730; padding: 5px; border-radius: 5px; }.event-card { font-size: 9px; padding: 3px; border-radius: 4px; color: white; margin-bottom: 2px; font-weight: bold; }</style>""", unsafe_allow_html=True)

    dias_n = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
    datas_s = [(seg + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(6)]

    for s in salas_de_aula_list:
        cols = st.columns([1.5, 2, 2, 2, 2, 2, 2])
        cols[0].markdown(f"<div class='resumo-sala'>{s}</div>", unsafe_allow_html=True)
        for i, d_s in enumerate(datas_s):
            with cols[i+1]:
                st.caption(f"{dias_n[i][:3]} {d_s[:5]}")
                if not df.empty:
                    evs = df[(df['sala'] == s) & (df['data'] == d_s)]
                    for _, r in evs.iterrows():
                        cor = "#1e40af" if "DA-FES" in r['origem'] else "#4b5563"
                        st.markdown(f"<div class='event-card' style='background:{cor}'>{r['horario_inicio']}<br>{r['origem']}</div>", unsafe_allow_html=True)

    st.markdown("---")
    s_det = st.selectbox("Consultar Sala específica:", ["Selecione..."] + salas_de_aula_list)
    if s_det != "Selecione...": exibir_tabela(s_det)

# ==========================================
# 6. EXECUÇÃO E RODAPÉ
# ==========================================

t1, t2, t3, t4 = st.tabs(abas_fixas)
with t1: exibir_tabela("Auditório Rio Amazonas")
with t2: exibir_tabela("Laboratório de Informática")
with t3: exibir_tabela("Sala de Reunião")
with t4: resumo_semanal_navegavel()

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
