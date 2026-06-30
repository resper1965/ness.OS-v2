#!/usr/bin/env bash
###############################################################################
# 01-pre-migration-housekeeping.sh
# 
# Descrição: Script de housekeeping pré-migração para reduzir o tamanho do
#            banco de dados antes da transferência Azure → Contabo.
#
# Execução:  Rodar no VM-Zabbix-02 (App Server - 52.146.5.10)
#
# O que faz:
#   - Conecta na API do Zabbix e configura políticas de retenção
#   - Define retenção de histórico para 90 dias
#   - Define retenção de trends para 365 dias
#   - Define retenção de eventos para 365 dias
#   - Executa housekeeping manualmente
#   - Mostra tamanho do banco antes/depois
#
# Uso: ./01-pre-migration-housekeeping.sh [--help] [--yes]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/housekeeping_$(date +%Y%m%d_%H%M%S).log"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# Configuração do Zabbix API (pode ser sobrescrita por variáveis de ambiente)
ZABBIX_API_URL="${ZABBIX_API_URL:-http://localhost/api_jsonrpc.php}"
ZABBIX_USER="${ZABBIX_USER:-Admin}"
ZABBIX_PASSWORD="${ZABBIX_PASSWORD:-zabbix}"

# Configuração do banco de dados
DB_HOST="${DB_HOST:-20.127.231.106}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-dbzabbix}"
DB_USER="${DB_USER:-usrzabbix}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Retenção em segundos
HISTORY_RETENTION=7776000    # 90 dias
TRENDS_RETENTION=31536000    # 365 dias
EVENTS_RETENTION=31536000    # 365 dias

# Flag de confirmação automática
AUTO_YES=false

# =============================================================================
# CORES PARA OUTPUT
# =============================================================================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m' # Sem cor

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

# Exibe mensagem de ajuda
show_help() {
    cat << EOF
${BOLD}USO:${NC}
    ${SCRIPT_NAME} [OPÇÕES]

${BOLD}DESCRIÇÃO:${NC}
    Script de housekeeping pré-migração. Configura políticas de retenção
    no Zabbix e executa limpeza para reduzir o tamanho do banco de dados
    antes da migração Azure → Contabo.

${BOLD}OPÇÕES:${NC}
    --help          Exibe esta mensagem de ajuda
    --yes           Pula confirmações interativas (modo automático)

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    ZABBIX_API_URL   URL da API Zabbix (padrão: http://localhost/api_jsonrpc.php)
    ZABBIX_USER      Usuário da API (padrão: Admin)
    ZABBIX_PASSWORD   Senha da API (padrão: zabbix)
    DB_HOST          Host do banco de dados (padrão: 20.127.231.106)
    DB_PORT          Porta do banco (padrão: 3306)
    DB_NAME          Nome do banco (padrão: dbzabbix)
    DB_USER          Usuário do banco (padrão: usrzabbix)
    DB_PASSWORD      Senha do banco (requerida)

${BOLD}EXEMPLOS:${NC}
    # Execução interativa (com confirmações)
    ./${SCRIPT_NAME}

    # Execução automática (sem confirmações)
    ./${SCRIPT_NAME} --yes

    # Com variáveis customizadas
    ZABBIX_PASSWORD=minha_senha DB_PASSWORD=db_senha ./${SCRIPT_NAME}

${BOLD}NOTAS:${NC}
    - Execute no VM-Zabbix-02 (App Server - 52.146.5.10)
    - Requer acesso à API do Zabbix e ao banco de dados
    - O housekeeping pode levar horas dependendo do volume de dados
    - Logs salvos em: ${LOG_DIR}/

EOF
    exit 0
}

# Função de log com timestamp
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    
    case "${level}" in
        INFO)    echo -e "${BLUE}[${timestamp}]${NC} ${GREEN}[INFO]${NC}  ${message}" ;;
        WARN)    echo -e "${BLUE}[${timestamp}]${NC} ${YELLOW}[WARN]${NC}  ${message}" ;;
        ERROR)   echo -e "${BLUE}[${timestamp}]${NC} ${RED}[ERRO]${NC}  ${message}" ;;
        STEP)    echo -e "${BLUE}[${timestamp}]${NC} ${CYAN}[STEP]${NC}  ${BOLD}${message}${NC}" ;;
        *)       echo -e "${BLUE}[${timestamp}]${NC} ${message}" ;;
    esac
    
    # Também grava no arquivo de log (sem códigos de cor)
    echo "[${timestamp}] [${level}] ${message}" | sed 's/\x1b\[[0-9;]*m//g' >> "${LOG_FILE}" 2>/dev/null || true
}

# Confirmação interativa
confirm() {
    local message="$1"
    if [[ "${AUTO_YES}" == true ]]; then
        log INFO "Auto-confirmação: ${message}"
        return 0
    fi
    
    echo -e "\n${YELLOW}⚠  ${message}${NC}"
    read -r -p "   Continuar? (s/N): " response
    case "${response}" in
        [sS]|[sS][iI][mM]) return 0 ;;
        *) 
            log WARN "Operação cancelada pelo usuário."
            return 1
            ;;
    esac
}

# Cleanup em caso de erro
cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log ERROR "Script interrompido com código de saída: ${exit_code}"
        log ERROR "Verifique o log em: ${LOG_FILE}"
    fi
    exit ${exit_code}
}

trap cleanup EXIT

# Chamada à API do Zabbix
zabbix_api_call() {
    local payload="$1"
    local response
    
    response=$(curl -s -X POST \
        -H "Content-Type: application/json-rpc" \
        -d "${payload}" \
        "${ZABBIX_API_URL}" 2>&1)
    
    # Verifica se houve erro na resposta
    if echo "${response}" | grep -q '"error"'; then
        local error_msg
        error_msg=$(echo "${response}" | python3 -c "import sys,json; e=json.load(sys.stdin).get('error',{}); print(f\"{e.get('message','')}: {e.get('data','')}\")" 2>/dev/null || echo "${response}")
        log ERROR "Erro na API Zabbix: ${error_msg}"
        return 1
    fi
    
    echo "${response}"
}

# Autenticação na API do Zabbix
zabbix_login() {
    log INFO "Autenticando na API do Zabbix..."
    
    local payload
    payload=$(cat << APIJSON
{
    "jsonrpc": "2.0",
    "method": "user.login",
    "params": {
        "username": "${ZABBIX_USER}",
        "password": "${ZABBIX_PASSWORD}"
    },
    "id": 1
}
APIJSON
    )
    
    local response
    response=$(zabbix_api_call "${payload}")
    
    AUTH_TOKEN=$(echo "${response}" | python3 -c "import sys,json; print(json.load(sys.stdin)['result'])" 2>/dev/null)
    
    if [[ -z "${AUTH_TOKEN}" ]]; then
        log ERROR "Falha na autenticação. Verifique credenciais."
        return 1
    fi
    
    log INFO "Autenticação bem-sucedida. Token obtido."
}

# Consulta tamanho do banco de dados
get_db_size() {
    local description="$1"
    log INFO "Consultando tamanho do banco de dados (${description})..."
    
    local size_query="SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb FROM information_schema.tables WHERE table_schema = '${DB_NAME}';"
    
    local size_gb
    if [[ -n "${DB_PASSWORD}" ]]; then
        size_gb=$(mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" -N -s -e "${size_query}" 2>/dev/null)
    else
        size_gb=$(mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -N -s -e "${size_query}" 2>/dev/null)
    fi
    
    if [[ -z "${size_gb}" ]]; then
        log WARN "Não foi possível obter o tamanho do banco. Verifique as credenciais do DB."
        echo "N/A"
        return 1
    fi
    
    echo "${size_gb}"
}

# Consulta tamanho detalhado por tabela (top 10)
get_top_tables() {
    log INFO "Consultando as 10 maiores tabelas..."
    
    local query="SELECT table_name, ROUND((data_length + index_length) / 1024 / 1024 / 1024, 2) AS size_gb FROM information_schema.tables WHERE table_schema = '${DB_NAME}' ORDER BY (data_length + index_length) DESC LIMIT 10;"
    
    if [[ -n "${DB_PASSWORD}" ]]; then
        mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -p"${DB_PASSWORD}" -e "${query}" 2>/dev/null
    else
        mysql -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" -e "${query}" 2>/dev/null
    fi
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            ;;
        --yes|-y)
            AUTO_YES=true
            shift
            ;;
        *)
            echo -e "${RED}Opção desconhecida: $1${NC}"
            echo "Use --help para ver as opções disponíveis."
            exit 1
            ;;
    esac
done

# =============================================================================
# INÍCIO DA EXECUÇÃO
# =============================================================================

# Cria diretório de log se não existir
mkdir -p "${LOG_DIR}" 2>/dev/null || {
    echo -e "${YELLOW}AVISO: Não foi possível criar ${LOG_DIR}. Usando /tmp/${NC}"
    LOG_DIR="/tmp"
}

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     HOUSEKEEPING PRÉ-MIGRAÇÃO - ZABBIX AZURE → CONTABO     ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Iniciando housekeeping pré-migração"
log INFO "API URL: ${ZABBIX_API_URL}"
log INFO "DB Host: ${DB_HOST}"
log INFO "Log: ${LOG_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Verificar conectividade
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 1/6: Verificando conectividade ═══"

# Verifica API do Zabbix
log INFO "Testando acesso à API do Zabbix..."
if curl -s -o /dev/null -w "%{http_code}" "${ZABBIX_API_URL}" | grep -q "200"; then
    log INFO "API do Zabbix acessível ✓"
else
    log ERROR "API do Zabbix não acessível em ${ZABBIX_API_URL}"
    exit 1
fi

# Verifica banco de dados
log INFO "Testando conexão com o banco de dados..."
if mysqladmin -h "${DB_HOST}" -P "${DB_PORT}" -u "${DB_USER}" ${DB_PASSWORD:+-p"${DB_PASSWORD}"} ping &>/dev/null; then
    log INFO "Banco de dados acessível ✓"
else
    log WARN "Não foi possível conectar ao banco. As métricas de tamanho não estarão disponíveis."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Autenticar na API
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 2/6: Autenticando na API do Zabbix ═══"
zabbix_login

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Tamanho atual do banco
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 3/6: Verificando tamanho atual do banco ═══"

SIZE_BEFORE=$(get_db_size "antes do housekeeping")
log INFO "Tamanho atual do banco: ${BOLD}${SIZE_BEFORE} GB${NC}"

echo ""
log INFO "Top 10 maiores tabelas:"
get_top_tables || log WARN "Não foi possível listar tabelas."

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Configurar políticas de retenção
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 4/6: Configurando políticas de retenção ═══"

echo -e "${CYAN}Configurações a serem aplicadas:${NC}"
echo -e "  • Histórico:  ${BOLD}90 dias${NC}  (${HISTORY_RETENTION} segundos)"
echo -e "  • Trends:     ${BOLD}365 dias${NC} (${TRENDS_RETENTION} segundos)"
echo -e "  • Eventos:    ${BOLD}365 dias${NC} (${EVENTS_RETENTION} segundos)"
echo ""

confirm "Aplicar novas políticas de retenção via API?" || exit 0

# Configura housekeeping via API
log INFO "Configurando housekeeping via API..."

# Atualiza configuração de housekeeping
# hk_history_global: 1 = override por item, hk_history: período padrão
local hk_payload
hk_payload=$(cat << APIJSON
{
    "jsonrpc": "2.0",
    "method": "housekeeping.update",
    "params": {
        "hk_history_global": "1",
        "hk_history": "${HISTORY_RETENTION}",
        "hk_trends_global": "1",
        "hk_trends": "${TRENDS_RETENTION}",
        "hk_events_mode": "1",
        "hk_events_trigger": "${EVENTS_RETENTION}",
        "hk_events_discovery": "${EVENTS_RETENTION}",
        "hk_events_autoreg": "${EVENTS_RETENTION}",
        "hk_events_internal": "${EVENTS_RETENTION}",
        "hk_services_mode": "1",
        "hk_services": "${EVENTS_RETENTION}"
    },
    "auth": "${AUTH_TOKEN}",
    "id": 2
}
APIJSON
)

response=$(zabbix_api_call "${hk_payload}")
if echo "${response}" | grep -q '"result"'; then
    log INFO "Políticas de retenção atualizadas com sucesso ✓"
else
    log ERROR "Falha ao atualizar políticas de retenção"
    log ERROR "Resposta: ${response}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5: Executar housekeeping manualmente
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 5/6: Executando housekeeping ═══"

echo -e "${YELLOW}⚠  ATENÇÃO: O housekeeping pode levar HORAS para concluir.${NC}"
echo -e "${YELLOW}   O banco tem ~${SIZE_BEFORE} GB e a limpeza de dados antigos é intensiva.${NC}"
echo -e "${YELLOW}   Recomenda-se executar fora do horário de pico.${NC}"
echo ""

confirm "Executar housekeeping agora? (pode levar várias horas)" || {
    log WARN "Housekeeping não executado. As políticas de retenção foram configuradas."
    log WARN "O Zabbix executará o housekeeping automaticamente nos próximos ciclos."
    echo ""
    log INFO "Alternativa: aguarde o housekeeping automático (executa a cada hora)"
    exit 0
}

log INFO "Executando housekeeping via API..."
log INFO "Isso pode levar várias horas. Acompanhe pelo log: ${LOG_FILE}"

# Executa housekeeping manualmente via API (Zabbix 6.4+)
hk_run_payload=$(cat << APIJSON
{
    "jsonrpc": "2.0",
    "method": "housekeeping.execute",
    "params": {},
    "auth": "${AUTH_TOKEN}",
    "id": 3
}
APIJSON
)

START_TIME=$(date +%s)
response=$(zabbix_api_call "${hk_run_payload}")
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if echo "${response}" | grep -q '"result"'; then
    log INFO "Housekeeping executado com sucesso ✓"
    log INFO "Duração: $((DURATION / 3600))h $((DURATION % 3600 / 60))m $((DURATION % 60))s"
else
    log WARN "Resposta do housekeeping: ${response}"
    log WARN "O housekeeping pode ter sido iniciado em background."
    log WARN "Verifique o log do Zabbix: /var/log/zabbix/zabbix_server.log"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Verificar tamanho após housekeeping
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 6/6: Verificando resultado ═══"

SIZE_AFTER=$(get_db_size "após housekeeping")
log INFO "Tamanho após housekeeping: ${BOLD}${SIZE_AFTER} GB${NC}"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    RESUMO DO HOUSEKEEPING                   ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} Tamanho ANTES:   ${CYAN}${SIZE_BEFORE} GB${NC}"
echo -e "${BOLD}║${NC} Tamanho DEPOIS:  ${CYAN}${SIZE_AFTER} GB${NC}"

if [[ "${SIZE_BEFORE}" != "N/A" && "${SIZE_AFTER}" != "N/A" ]]; then
    SAVED=$(echo "${SIZE_BEFORE} - ${SIZE_AFTER}" | bc 2>/dev/null || echo "N/A")
    if [[ "${SAVED}" != "N/A" ]]; then
        echo -e "${BOLD}║${NC} Espaço liberado: ${GREEN}${SAVED} GB${NC}"
    fi
fi

echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} Retenção configurada:"
echo -e "${BOLD}║${NC}   • Histórico: 90 dias"
echo -e "${BOLD}║${NC}   • Trends:    365 dias"
echo -e "${BOLD}║${NC}   • Eventos:   365 dias"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} Log: ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Housekeeping concluído. Próximo passo: executar 02-dump-database.sh no VM-Zabbix-01"
log INFO "Script finalizado com sucesso."
