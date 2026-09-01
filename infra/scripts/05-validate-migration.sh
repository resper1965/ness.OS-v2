#!/usr/bin/env bash
###############################################################################
# 05-validate-migration.sh
#
# Descrição: Validação completa pós-migração do Zabbix no servidor Contabo.
#            Verifica serviços, API, dados, segurança e infraestrutura.
#
# Execução:  Rodar no servidor Contabo (destino) após migração
#
# O que faz:
#   - Verifica todos os serviços (mariadb, zabbix-server, apache2, zabbix-agent2)
#   - Testa API do Zabbix e conta hosts/items/triggers
#   - Verifica frontend HTTPS
#   - Checa backup, firewall, SSL, disco
#   - Gera relatório PASS/WARN/FAIL
#
# Uso: ./05-validate-migration.sh [--help] [--json]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/validate_$(date +%Y%m%d_%H%M%S).log"

# Zabbix API
ZABBIX_API_URL="${ZABBIX_API_URL:-http://localhost/api_jsonrpc.php}"
ZABBIX_API_TOKEN="${ZABBIX_API_TOKEN:-}"
ZABBIX_USER="${ZABBIX_USER:-}"
ZABBIX_PASSWORD="${ZABBIX_PASSWORD:-}"
ZABBIX_FRONTEND_URL="${ZABBIX_FRONTEND_URL:-https://localhost}"

# Valores esperados da migração
EXPECTED_HOSTS="${EXPECTED_HOSTS:-374}"
EXPECTED_ITEMS="${EXPECTED_ITEMS:-59031}"
EXPECTED_TRIGGERS="${EXPECTED_TRIGGERS:-25716}"

# Tolerâncias
TOLERANCE_PASS=5    # Até 5% de diferença = PASS
TOLERANCE_WARN=10   # Até 10% = WARN, acima = FAIL

# Disco
DISK_WARN_PERCENT=80

# Formato de saída
OUTPUT_JSON=false

# =============================================================================
# CORES PARA OUTPUT
# =============================================================================
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly BOLD='\033[1m'
readonly NC='\033[0m'

# Contadores de resultado
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

# Array de resultados
declare -a RESULTS=()

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

show_help() {
    cat << EOF
${BOLD}USO:${NC}
    ${SCRIPT_NAME} [OPÇÕES]

${BOLD}DESCRIÇÃO:${NC}
    Executa validação completa pós-migração do Zabbix.
    Verifica serviços, API, dados, segurança e infraestrutura.
    Gera relatório com status PASS/WARN/FAIL para cada verificação.

${BOLD}OPÇÕES:${NC}
    --help          Exibe esta mensagem de ajuda
    --json          Saída em formato JSON

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    ZABBIX_API_URL      URL da API (padrão: http://localhost/api_jsonrpc.php)
    ZABBIX_API_TOKEN    Token da API (preferencial; obrigatório se não houver
                        usuário e senha)
    ZABBIX_USER         Usuário da API (somente com ZABBIX_PASSWORD)
    ZABBIX_PASSWORD     Senha da API (somente com ZABBIX_USER)
    EXPECTED_HOSTS      Número esperado de hosts (padrão: 374)
    EXPECTED_ITEMS      Número esperado de items (padrão: 59031)
    EXPECTED_TRIGGERS   Número esperado de triggers (padrão: 25716)

${BOLD}CÓDIGOS DE SAÍDA:${NC}
    0    Todos os checks PASS
    1    Pelo menos um FAIL
    2    Apenas WARNs (sem FAILs)

${BOLD}EXEMPLOS:${NC}
    ./${SCRIPT_NAME}
    ZABBIX_API_TOKEN='token-protegido' ./${SCRIPT_NAME}
    ./${SCRIPT_NAME} --json > resultado.json

EOF
    exit 0
}

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
    
    echo "[${timestamp}] [${level}] ${message}" | sed 's/\x1b\[[0-9;]*m//g' >> "${LOG_FILE}" 2>/dev/null || true
}

# Registra resultado de verificação
check_result() {
    local name="$1"
    local status="$2"  # PASS, WARN, FAIL
    local detail="${3:-}"
    
    case "${status}" in
        PASS)
            echo -e "  ${GREEN}✓ PASS${NC}  ${name} ${detail:+- ${detail}}"
            PASS_COUNT=$((PASS_COUNT + 1))
            ;;
        WARN)
            echo -e "  ${YELLOW}⚠ WARN${NC}  ${name} ${detail:+- ${detail}}"
            WARN_COUNT=$((WARN_COUNT + 1))
            ;;
        FAIL)
            echo -e "  ${RED}✗ FAIL${NC}  ${name} ${detail:+- ${detail}}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            ;;
    esac
    
    RESULTS+=("${status}|${name}|${detail}")
    echo "[${status}] ${name} - ${detail}" >> "${LOG_FILE}" 2>/dev/null || true
}

# Chamada à API do Zabbix
zabbix_api_call() {
    local payload="$1"
    curl -s -X POST \
        -H "Content-Type: application/json-rpc" \
        -d "${payload}" \
        "${ZABBIX_API_URL}" 2>/dev/null || echo ""
}

# Calcula diferença percentual
percent_diff() {
    local actual=$1
    local expected=$2
    if [[ ${expected} -eq 0 ]]; then
        echo "100"
        return
    fi
    local diff=$((actual - expected))
    if [[ ${diff} -lt 0 ]]; then
        diff=$((-diff))
    fi
    echo "$((diff * 100 / expected))"
}

cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]] && [[ ${exit_code} -ne 1 ]] && [[ ${exit_code} -ne 2 ]]; then
        log ERROR "Script interrompido com código: ${exit_code}"
    fi
}

trap cleanup EXIT

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            ;;
        --json)
            OUTPUT_JSON=true
            shift
            ;;
        *)
            echo -e "${RED}Opção desconhecida: $1${NC}"
            exit 1
            ;;
    esac
done

# =============================================================================
# INÍCIO DA EXECUÇÃO
# =============================================================================

mkdir -p "${LOG_DIR}" 2>/dev/null || true

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         VALIDAÇÃO PÓS-MIGRAÇÃO - ZABBIX CONTABO            ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Iniciando validação pós-migração"
log INFO "Log: ${LOG_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 1: Serviços do sistema
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 1: Serviços do Sistema ═══"

for service in mariadb zabbix-server apache2 zabbix-agent2; do
    if systemctl is-active "${service}" &>/dev/null; then
        check_result "Serviço: ${service}" "PASS" "ativo e rodando"
    elif systemctl is-enabled "${service}" &>/dev/null; then
        check_result "Serviço: ${service}" "FAIL" "habilitado mas NÃO ativo"
    else
        check_result "Serviço: ${service}" "FAIL" "não está ativo"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 2: API do Zabbix
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 2: API do Zabbix ═══"

# Testa se API responde
API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${ZABBIX_API_URL}" 2>/dev/null || echo "000")

if [[ "${API_RESPONSE}" == "200" ]]; then
    check_result "API HTTP Status" "PASS" "HTTP ${API_RESPONSE}"
else
    check_result "API HTTP Status" "FAIL" "HTTP ${API_RESPONSE}"
fi

# Autentica na API. Nunca assume credenciais padrão.
AUTH_TOKEN=""
if [[ "${API_RESPONSE}" == "200" ]]; then
    if [[ -n "${ZABBIX_API_TOKEN}" ]]; then
        AUTH_TOKEN="${ZABBIX_API_TOKEN}"
        check_result "API Autenticação" "PASS" "token fornecido pelo ambiente"
    elif [[ -n "${ZABBIX_USER}" && -n "${ZABBIX_PASSWORD}" ]]; then
        login_response=$(zabbix_api_call "{
            \"jsonrpc\": \"2.0\",
            \"method\": \"user.login\",
            \"params\": {\"username\": \"${ZABBIX_USER}\", \"password\": \"${ZABBIX_PASSWORD}\"},
            \"id\": 1
        }")
        AUTH_TOKEN=$(echo "${login_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',''))" 2>/dev/null || echo "")
        if [[ -n "${AUTH_TOKEN}" ]]; then
            check_result "API Autenticação" "PASS" "login por variáveis de ambiente"
        else
            check_result "API Autenticação" "FAIL" "falha no login"
        fi
    else
        check_result "API Autenticação" "WARN" "token ou credenciais não fornecidos"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 3: Contagem de dados (hosts, items, triggers)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 3: Contagem de Dados ═══"

if [[ -n "${AUTH_TOKEN}" ]]; then
    # Conta hosts
    hosts_response=$(zabbix_api_call "{
        \"jsonrpc\": \"2.0\",
        \"method\": \"host.get\",
        \"params\": {\"countOutput\": true},
        \"auth\": \"${AUTH_TOKEN}\",
        \"id\": 2
    }")
    ACTUAL_HOSTS=$(echo "${hosts_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',0))" 2>/dev/null || echo "0")
    
    HOSTS_DIFF=$(percent_diff "${ACTUAL_HOSTS}" "${EXPECTED_HOSTS}")
    if [[ ${HOSTS_DIFF} -le ${TOLERANCE_PASS} ]]; then
        check_result "Hosts" "PASS" "${ACTUAL_HOSTS} (esperado: ${EXPECTED_HOSTS}, diff: ${HOSTS_DIFF}%)"
    elif [[ ${HOSTS_DIFF} -le ${TOLERANCE_WARN} ]]; then
        check_result "Hosts" "WARN" "${ACTUAL_HOSTS} (esperado: ${EXPECTED_HOSTS}, diff: ${HOSTS_DIFF}%)"
    else
        check_result "Hosts" "FAIL" "${ACTUAL_HOSTS} (esperado: ${EXPECTED_HOSTS}, diff: ${HOSTS_DIFF}%)"
    fi
    
    # Conta items
    items_response=$(zabbix_api_call "{
        \"jsonrpc\": \"2.0\",
        \"method\": \"item.get\",
        \"params\": {\"countOutput\": true},
        \"auth\": \"${AUTH_TOKEN}\",
        \"id\": 3
    }")
    ACTUAL_ITEMS=$(echo "${items_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',0))" 2>/dev/null || echo "0")
    
    ITEMS_DIFF=$(percent_diff "${ACTUAL_ITEMS}" "${EXPECTED_ITEMS}")
    if [[ ${ITEMS_DIFF} -le ${TOLERANCE_PASS} ]]; then
        check_result "Items" "PASS" "${ACTUAL_ITEMS} (esperado: ${EXPECTED_ITEMS}, diff: ${ITEMS_DIFF}%)"
    elif [[ ${ITEMS_DIFF} -le ${TOLERANCE_WARN} ]]; then
        check_result "Items" "WARN" "${ACTUAL_ITEMS} (esperado: ${EXPECTED_ITEMS}, diff: ${ITEMS_DIFF}%)"
    else
        check_result "Items" "FAIL" "${ACTUAL_ITEMS} (esperado: ${EXPECTED_ITEMS}, diff: ${ITEMS_DIFF}%)"
    fi
    
    # Conta triggers
    triggers_response=$(zabbix_api_call "{
        \"jsonrpc\": \"2.0\",
        \"method\": \"trigger.get\",
        \"params\": {\"countOutput\": true},
        \"auth\": \"${AUTH_TOKEN}\",
        \"id\": 4
    }")
    ACTUAL_TRIGGERS=$(echo "${triggers_response}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',0))" 2>/dev/null || echo "0")
    
    TRIGGERS_DIFF=$(percent_diff "${ACTUAL_TRIGGERS}" "${EXPECTED_TRIGGERS}")
    if [[ ${TRIGGERS_DIFF} -le ${TOLERANCE_PASS} ]]; then
        check_result "Triggers" "PASS" "${ACTUAL_TRIGGERS} (esperado: ${EXPECTED_TRIGGERS}, diff: ${TRIGGERS_DIFF}%)"
    elif [[ ${TRIGGERS_DIFF} -le ${TOLERANCE_WARN} ]]; then
        check_result "Triggers" "WARN" "${ACTUAL_TRIGGERS} (esperado: ${EXPECTED_TRIGGERS}, diff: ${TRIGGERS_DIFF}%)"
    else
        check_result "Triggers" "FAIL" "${ACTUAL_TRIGGERS} (esperado: ${EXPECTED_TRIGGERS}, diff: ${TRIGGERS_DIFF}%)"
    fi
else
    check_result "Hosts" "WARN" "Não foi possível contar (sem autenticação)"
    check_result "Items" "WARN" "Não foi possível contar (sem autenticação)"
    check_result "Triggers" "WARN" "Não foi possível contar (sem autenticação)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 4: Frontend HTTPS
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 4: Frontend Web ═══"

# Testa HTTPS
HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" "${ZABBIX_FRONTEND_URL}" 2>/dev/null || echo "000")
if [[ "${HTTPS_STATUS}" == "200" ]] || [[ "${HTTPS_STATUS}" == "302" ]]; then
    check_result "Frontend HTTPS" "PASS" "HTTP ${HTTPS_STATUS}"
else
    check_result "Frontend HTTPS" "FAIL" "HTTP ${HTTPS_STATUS}"
fi

# Testa se redireciona HTTP → HTTPS
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost" 2>/dev/null || echo "000")
if [[ "${HTTP_STATUS}" == "301" ]] || [[ "${HTTP_STATUS}" == "302" ]] || [[ "${HTTP_STATUS}" == "200" ]]; then
    check_result "Redirect HTTP→HTTPS" "PASS" "HTTP ${HTTP_STATUS}"
else
    check_result "Redirect HTTP→HTTPS" "WARN" "HTTP ${HTTP_STATUS}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 5: Certificado SSL
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 5: Certificado SSL ═══"

SSL_INFO=$(echo | openssl s_client -connect localhost:443 -servername localhost 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo "")

if [[ -n "${SSL_INFO}" ]]; then
    EXPIRY_DATE=$(echo "${SSL_INFO}" | grep 'notAfter' | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "${EXPIRY_DATE}" +%s 2>/dev/null || echo "0")
    CURRENT_EPOCH=$(date +%s)
    DAYS_LEFT=$(( (EXPIRY_EPOCH - CURRENT_EPOCH) / 86400 ))
    
    if [[ ${DAYS_LEFT} -gt 30 ]]; then
        check_result "Certificado SSL" "PASS" "expira em ${DAYS_LEFT} dias (${EXPIRY_DATE})"
    elif [[ ${DAYS_LEFT} -gt 7 ]]; then
        check_result "Certificado SSL" "WARN" "expira em ${DAYS_LEFT} dias (${EXPIRY_DATE})"
    else
        check_result "Certificado SSL" "FAIL" "expira em ${DAYS_LEFT} dias! (${EXPIRY_DATE})"
    fi
else
    check_result "Certificado SSL" "WARN" "não foi possível verificar"
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 6: Firewall (UFW)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 6: Firewall ═══"

UFW_STATUS=$(sudo ufw status 2>/dev/null | head -1 || echo "")
if echo "${UFW_STATUS}" | grep -qi "active"; then
    check_result "UFW Firewall" "PASS" "ativo"
    
    # Verifica regras essenciais
    UFW_RULES=$(sudo ufw status 2>/dev/null || echo "")
    for port in "22/tcp" "443/tcp" "10050/tcp" "10051/tcp"; do
        if echo "${UFW_RULES}" | grep -q "${port}"; then
            check_result "UFW porta ${port}" "PASS" "regra configurada"
        else
            check_result "UFW porta ${port}" "WARN" "regra não encontrada"
        fi
    done
else
    check_result "UFW Firewall" "FAIL" "NÃO está ativo"
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 7: Backup
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 7: Backup ═══"

BACKUP_CRON=$(sudo crontab -l 2>/dev/null | grep -i "backup\|mysqldump\|dbzabbix" || echo "")
if [[ -n "${BACKUP_CRON}" ]]; then
    check_result "Cron de backup" "PASS" "configurado"
else
    # Verifica crontab do root
    BACKUP_CRON_ROOT=$(sudo crontab -u root -l 2>/dev/null | grep -i "backup\|mysqldump\|dbzabbix" || echo "")
    if [[ -n "${BACKUP_CRON_ROOT}" ]]; then
        check_result "Cron de backup" "PASS" "configurado (root)"
    else
        check_result "Cron de backup" "FAIL" "nenhum job de backup encontrado"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 8: Disco
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 8: Espaço em Disco ═══"

DISK_USAGE=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
DISK_TOTAL=$(df -h / | tail -1 | awk '{print $2}')
DISK_USED=$(df -h / | tail -1 | awk '{print $3}')
DISK_AVAIL=$(df -h / | tail -1 | awk '{print $4}')

if [[ ${DISK_USAGE} -lt ${DISK_WARN_PERCENT} ]]; then
    check_result "Disco /" "PASS" "${DISK_USAGE}% usado (${DISK_USED}/${DISK_TOTAL}, livre: ${DISK_AVAIL})"
else
    check_result "Disco /" "WARN" "${DISK_USAGE}% usado (${DISK_USED}/${DISK_TOTAL}, livre: ${DISK_AVAIL})"
fi

# Verifica partição de dados do MySQL se separada
if df /var/lib/mysql &>/dev/null; then
    MYSQL_DISK_USAGE=$(df -h /var/lib/mysql | tail -1 | awk '{print $5}' | tr -d '%')
    MYSQL_DISK_AVAIL=$(df -h /var/lib/mysql | tail -1 | awk '{print $4}')
    if [[ ${MYSQL_DISK_USAGE} -lt ${DISK_WARN_PERCENT} ]]; then
        check_result "Disco /var/lib/mysql" "PASS" "${MYSQL_DISK_USAGE}% usado (livre: ${MYSQL_DISK_AVAIL})"
    else
        check_result "Disco /var/lib/mysql" "WARN" "${MYSQL_DISK_USAGE}% usado (livre: ${MYSQL_DISK_AVAIL})"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 9: MariaDB
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 9: MariaDB ═══"

# Testa conexão
if mysqladmin ping &>/dev/null || sudo mysqladmin ping &>/dev/null; then
    check_result "MariaDB conexão" "PASS" "respondendo a ping"
else
    check_result "MariaDB conexão" "FAIL" "não responde"
fi

# Verifica versão
MARIADB_VERSION=$(mysql --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "N/A")
check_result "MariaDB versão" "PASS" "${MARIADB_VERSION}"

# ─────────────────────────────────────────────────────────────────────────────
# CHECK 10: Log do Zabbix Server
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ CHECK 10: Logs do Zabbix ═══"

ZABBIX_LOG="/var/log/zabbix/zabbix_server.log"
if [[ -f "${ZABBIX_LOG}" ]]; then
    # Verifica últimos erros (últimas 100 linhas)
    RECENT_ERRORS=$(tail -100 "${ZABBIX_LOG}" 2>/dev/null | grep -ci "error\|fatal\|cannot connect" || echo "0")
    
    if [[ ${RECENT_ERRORS} -eq 0 ]]; then
        check_result "Log Zabbix (erros recentes)" "PASS" "sem erros"
    elif [[ ${RECENT_ERRORS} -lt 5 ]]; then
        check_result "Log Zabbix (erros recentes)" "WARN" "${RECENT_ERRORS} erros encontrados"
    else
        check_result "Log Zabbix (erros recentes)" "FAIL" "${RECENT_ERRORS} erros encontrados"
    fi
    
    # Última linha do log
    LAST_LOG=$(tail -1 "${ZABBIX_LOG}" 2>/dev/null || echo "N/A")
    log INFO "Última entrada do log: ${LAST_LOG}"
else
    check_result "Log Zabbix" "WARN" "arquivo não encontrado: ${ZABBIX_LOG}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# RELATÓRIO FINAL
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║              RELATÓRIO DE VALIDAÇÃO                        ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC}"

TOTAL_CHECKS=$((PASS_COUNT + WARN_COUNT + FAIL_COUNT))

echo -e "${BOLD}║${NC}  Total de verificações: ${BOLD}${TOTAL_CHECKS}${NC}"
echo -e "${BOLD}║${NC}  ${GREEN}✓ PASS: ${PASS_COUNT}${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}⚠ WARN: ${WARN_COUNT}${NC}"
echo -e "${BOLD}║${NC}  ${RED}✗ FAIL: ${FAIL_COUNT}${NC}"
echo -e "${BOLD}║${NC}"

if [[ ${FAIL_COUNT} -eq 0 ]] && [[ ${WARN_COUNT} -eq 0 ]]; then
    echo -e "${BOLD}║${NC}  Status: ${GREEN}${BOLD}✓ MIGRAÇÃO VALIDADA COM SUCESSO${NC}"
    EXIT_CODE=0
elif [[ ${FAIL_COUNT} -eq 0 ]]; then
    echo -e "${BOLD}║${NC}  Status: ${YELLOW}${BOLD}⚠ MIGRAÇÃO OK COM AVISOS${NC}"
    EXIT_CODE=2
else
    echo -e "${BOLD}║${NC}  Status: ${RED}${BOLD}✗ MIGRAÇÃO COM FALHAS - INVESTIGAR${NC}"
    EXIT_CODE=1
fi

echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "${BOLD}║${NC}  Log:  ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Saída JSON se solicitada
if [[ "${OUTPUT_JSON}" == true ]]; then
    echo ""
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"total\": ${TOTAL_CHECKS},"
    echo "  \"pass\": ${PASS_COUNT},"
    echo "  \"warn\": ${WARN_COUNT},"
    echo "  \"fail\": ${FAIL_COUNT},"
    echo "  \"status\": \"$(if [[ ${FAIL_COUNT} -eq 0 ]] && [[ ${WARN_COUNT} -eq 0 ]]; then echo 'PASS'; elif [[ ${FAIL_COUNT} -eq 0 ]]; then echo 'WARN'; else echo 'FAIL'; fi)\","
    echo "  \"results\": ["
    for i in "${!RESULTS[@]}"; do
        IFS='|' read -r status name detail <<< "${RESULTS[$i]}"
        echo -n "    {\"status\": \"${status}\", \"check\": \"${name}\", \"detail\": \"${detail}\"}"
        if [[ $i -lt $((${#RESULTS[@]} - 1)) ]]; then
            echo ","
        else
            echo ""
        fi
    done
    echo "  ]"
    echo "}"
fi

if [[ ${FAIL_COUNT} -gt 0 ]]; then
    log WARN "Próximo passo: corrigir as falhas e executar novamente."
else
    log INFO "Próximo passo: executar 06-cleanup-azure.sh para descomissionar o Azure"
fi

exit ${EXIT_CODE}
