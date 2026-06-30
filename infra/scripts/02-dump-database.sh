#!/usr/bin/env bash
###############################################################################
# 02-dump-database.sh
#
# Descrição: Realiza o dump do banco de dados Zabbix no Azure para migração.
#            Para o Zabbix Server antes do dump para garantir consistência.
#
# Execução:  Rodar no VM-Zabbix-01 (DB Server - 20.127.231.106)
#
# O que faz:
#   - Para o Zabbix Server no VM-Zabbix-02 via SSH
#   - Executa mysqldump com opções de consistência
#   - Comprime com pigz (gzip paralelo)
#   - Calcula checksum MD5
#   - Exibe tamanho e tempo estimado de transferência
#
# Uso: ./02-dump-database.sh [--help] [--skip-stop]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/dump_$(date +%Y%m%d).log"
readonly TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
readonly BACKUP_DIR="/backup/zabbix-migration"
readonly DUMP_FILE="${BACKUP_DIR}/dbzabbix_${TIMESTAMP}.sql.gz"
readonly MD5_FILE="${DUMP_FILE}.md5"

# Servidores
readonly APP_SERVER="52.146.5.10"
readonly APP_USER="ness_admin"

# Banco de dados
DB_NAME="${DB_NAME:-dbzabbix}"
DB_USER="${DB_USER:-usrzabbix}"
DB_PASSWORD="${DB_PASSWORD:-}"

# Opções
SKIP_STOP=false

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

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

show_help() {
    cat << EOF
${BOLD}USO:${NC}
    ${SCRIPT_NAME} [OPÇÕES]

${BOLD}DESCRIÇÃO:${NC}
    Realiza o dump do banco de dados Zabbix (MariaDB) para migração.
    O script para o Zabbix Server antes do dump, executa o mysqldump
    com compressão paralela e calcula o checksum MD5.

${BOLD}OPÇÕES:${NC}
    --help          Exibe esta mensagem de ajuda
    --skip-stop     Não para o Zabbix Server (NÃO RECOMENDADO)

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    DB_NAME         Nome do banco (padrão: dbzabbix)
    DB_USER         Usuário do banco (padrão: usrzabbix)
    DB_PASSWORD     Senha do banco (requerida)

${BOLD}SAÍDA:${NC}
    Dump: ${BACKUP_DIR}/dbzabbix_YYYYMMDD_HHMMSS.sql.gz
    MD5:  ${BACKUP_DIR}/dbzabbix_YYYYMMDD_HHMMSS.sql.gz.md5
    Log:  ${LOG_DIR}/dump_YYYYMMDD.log

${BOLD}EXEMPLOS:${NC}
    DB_PASSWORD=senha_db ./${SCRIPT_NAME}
    DB_PASSWORD=senha_db ./${SCRIPT_NAME} --skip-stop

${BOLD}NOTAS:${NC}
    - Execute no VM-Zabbix-01 (DB Server - 20.127.231.106)
    - Requer acesso SSH ao VM-Zabbix-02 para parar o Zabbix Server
    - O dump de 452 GB pode levar 2-4 horas
    - Certifique-se de ter espaço livre suficiente (mínimo 150 GB)

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

# Confirmação interativa
confirm() {
    local message="$1"
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

# Formata bytes em formato legível
format_size() {
    local bytes=$1
    if [[ ${bytes} -ge 1073741824 ]]; then
        echo "$(echo "scale=2; ${bytes}/1073741824" | bc) GB"
    elif [[ ${bytes} -ge 1048576 ]]; then
        echo "$(echo "scale=2; ${bytes}/1048576" | bc) MB"
    else
        echo "${bytes} bytes"
    fi
}

# Estima tempo de transferência
estimate_transfer_time() {
    local size_bytes=$1
    local speed_mbps=$2
    local speed_bytes=$((speed_mbps * 1000000 / 8))
    local seconds=$((size_bytes / speed_bytes))
    local hours=$((seconds / 3600))
    local minutes=$(( (seconds % 3600) / 60))
    echo "${hours}h ${minutes}m"
}

# Cleanup em caso de erro
cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log ERROR "Script interrompido com código de saída: ${exit_code}"
        
        # Se o dump falhou, remove arquivo parcial
        if [[ -f "${DUMP_FILE}" ]]; then
            log WARN "Removendo dump parcial: ${DUMP_FILE}"
            rm -f "${DUMP_FILE}" "${MD5_FILE}"
        fi
        
        # Tenta reiniciar o Zabbix Server se foi parado
        if [[ "${SKIP_STOP}" == false ]]; then
            log WARN "Tentando reiniciar o Zabbix Server no App Server..."
            ssh -o ConnectTimeout=10 "${APP_USER}@${APP_SERVER}" \
                'sudo systemctl start zabbix-server' 2>/dev/null || \
                log ERROR "ATENÇÃO: Não foi possível reiniciar o Zabbix Server automaticamente!"
        fi
        
        log ERROR "Verifique o log em: ${LOG_FILE}"
    fi
    exit ${exit_code}
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
        --skip-stop)
            SKIP_STOP=true
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
# VALIDAÇÕES
# =============================================================================

# Verifica se a senha do DB foi fornecida
if [[ -z "${DB_PASSWORD}" ]]; then
    echo -e "${RED}ERRO: DB_PASSWORD não definida.${NC}"
    echo "Use: DB_PASSWORD=sua_senha ./${SCRIPT_NAME}"
    exit 1
fi

# Cria diretórios necessários
mkdir -p "${LOG_DIR}" 2>/dev/null || true
mkdir -p "${BACKUP_DIR}" 2>/dev/null || {
    log ERROR "Não foi possível criar o diretório de backup: ${BACKUP_DIR}"
    exit 1
}

# =============================================================================
# INÍCIO DA EXECUÇÃO
# =============================================================================

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       DUMP DO BANCO DE DADOS - MIGRAÇÃO ZABBIX             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Iniciando dump do banco de dados"
log INFO "Banco: ${DB_NAME} | Usuário: ${DB_USER}"
log INFO "Arquivo de saída: ${DUMP_FILE}"
log INFO "Log: ${LOG_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Verificar espaço em disco
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 1/6: Verificando espaço em disco ═══"

AVAILABLE_SPACE=$(df -B1 "${BACKUP_DIR}" | tail -1 | awk '{print $4}')
AVAILABLE_GB=$(echo "scale=2; ${AVAILABLE_SPACE}/1073741824" | bc)
log INFO "Espaço disponível em ${BACKUP_DIR}: ${AVAILABLE_GB} GB"

# Estima tamanho comprimido (~20-30% do original para dados Zabbix)
ESTIMATED_COMPRESSED_GB=$(echo "scale=2; 452 * 0.25" | bc)
log INFO "Tamanho estimado do dump comprimido: ~${ESTIMATED_COMPRESSED_GB} GB"

if (( $(echo "${AVAILABLE_GB} < ${ESTIMATED_COMPRESSED_GB}" | bc -l) )); then
    log ERROR "Espaço insuficiente! Necessário: ~${ESTIMATED_COMPRESSED_GB} GB, Disponível: ${AVAILABLE_GB} GB"
    exit 1
fi
log INFO "Espaço em disco suficiente ✓"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Verificar ferramentas necessárias
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 2/6: Verificando ferramentas ═══"

# Verifica mysqldump
if ! command -v mysqldump &>/dev/null; then
    log ERROR "mysqldump não encontrado. Instale o mariadb-client."
    exit 1
fi
log INFO "mysqldump encontrado ✓"

# Verifica pigz (compressão paralela) com fallback para gzip
COMPRESS_CMD="pigz"
if ! command -v pigz &>/dev/null; then
    log WARN "pigz não encontrado. Usando gzip (mais lento)."
    log WARN "Instale com: apt install pigz"
    COMPRESS_CMD="gzip"
else
    PIGZ_THREADS=$(nproc)
    COMPRESS_CMD="pigz -p ${PIGZ_THREADS}"
    log INFO "pigz encontrado (${PIGZ_THREADS} threads) ✓"
fi

# Verifica md5sum
if ! command -v md5sum &>/dev/null; then
    log ERROR "md5sum não encontrado."
    exit 1
fi
log INFO "md5sum encontrado ✓"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Parar Zabbix Server
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 3/6: Parando Zabbix Server ═══"

if [[ "${SKIP_STOP}" == true ]]; then
    log WARN "Flag --skip-stop ativada. Zabbix Server NÃO será parado."
    log WARN "O dump pode conter inconsistências!"
else
    log INFO "Parando Zabbix Server no App Server (${APP_SERVER})..."
    
    confirm "Parar o Zabbix Server? O monitoramento ficará indisponível." || exit 0
    
    # Verifica conectividade SSH
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${APP_USER}@${APP_SERVER}" "echo ok" &>/dev/null; then
        log ERROR "Não foi possível conectar via SSH ao ${APP_SERVER}"
        log ERROR "Verifique a chave SSH e conectividade."
        exit 1
    fi
    
    # Para o Zabbix Server
    ssh "${APP_USER}@${APP_SERVER}" 'sudo systemctl stop zabbix-server'
    
    # Verifica se parou
    sleep 3
    ZBX_STATUS=$(ssh "${APP_USER}@${APP_SERVER}" 'systemctl is-active zabbix-server 2>/dev/null' || true)
    
    if [[ "${ZBX_STATUS}" == "inactive" ]] || [[ "${ZBX_STATUS}" == "dead" ]]; then
        log INFO "Zabbix Server parado com sucesso ✓"
    else
        log ERROR "Zabbix Server ainda está rodando (status: ${ZBX_STATUS})"
        log ERROR "Pare manualmente: ssh ${APP_USER}@${APP_SERVER} 'sudo systemctl stop zabbix-server'"
        exit 1
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Executar mysqldump
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 4/6: Executando mysqldump ═══"

log INFO "Iniciando mysqldump do banco '${DB_NAME}'..."
log INFO "Compressão: ${COMPRESS_CMD}"
log INFO "Arquivo de saída: ${DUMP_FILE}"
log WARN "ATENÇÃO: Este processo pode levar 2-4 horas para 452 GB."
echo ""

DUMP_START=$(date +%s)

# Executa mysqldump com compressão
mysqldump \
    --user="${DB_USER}" \
    --password="${DB_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --quick \
    --max_allowed_packet=1G \
    --set-gtid-purged=OFF \
    --hex-blob \
    "${DB_NAME}" 2>>"${LOG_FILE}" | ${COMPRESS_CMD} > "${DUMP_FILE}"

DUMP_END=$(date +%s)
DUMP_DURATION=$((DUMP_END - DUMP_START))

log INFO "mysqldump concluído ✓"
log INFO "Duração: $((DUMP_DURATION / 3600))h $((DUMP_DURATION % 3600 / 60))m $((DUMP_DURATION % 60))s"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5: Calcular checksum e tamanho
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 5/6: Calculando checksum ═══"

# Calcula MD5
log INFO "Calculando MD5 checksum..."
MD5_START=$(date +%s)
md5sum "${DUMP_FILE}" > "${MD5_FILE}"
MD5_END=$(date +%s)

MD5_VALUE=$(cat "${MD5_FILE}" | awk '{print $1}')
log INFO "MD5: ${MD5_VALUE}"
log INFO "Checksum salvo em: ${MD5_FILE}"
log INFO "Tempo de cálculo: $((MD5_END - MD5_START))s"

# Tamanho do arquivo
FILE_SIZE=$(stat -c%s "${DUMP_FILE}" 2>/dev/null || stat -f%z "${DUMP_FILE}" 2>/dev/null)
FILE_SIZE_HUMAN=$(format_size "${FILE_SIZE}")
log INFO "Tamanho do dump comprimido: ${BOLD}${FILE_SIZE_HUMAN}${NC}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Resumo e estimativas de transferência
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 6/6: Resumo ═══"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    RESUMO DO DUMP                          ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} Banco:           ${CYAN}${DB_NAME}${NC}"
echo -e "${BOLD}║${NC} Arquivo:         ${CYAN}${DUMP_FILE}${NC}"
echo -e "${BOLD}║${NC} Tamanho:         ${CYAN}${FILE_SIZE_HUMAN}${NC}"
echo -e "${BOLD}║${NC} MD5:             ${CYAN}${MD5_VALUE}${NC}"
echo -e "${BOLD}║${NC} Duração:         ${CYAN}$((DUMP_DURATION / 3600))h $((DUMP_DURATION % 3600 / 60))m $((DUMP_DURATION % 60))s${NC}"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} ${BOLD}Tempo estimado de transferência:${NC}"
echo -e "${BOLD}║${NC}   50 Mbps:  ~$(estimate_transfer_time "${FILE_SIZE}" 50)"
echo -e "${BOLD}║${NC}  100 Mbps:  ~$(estimate_transfer_time "${FILE_SIZE}" 100)"
echo -e "${BOLD}║${NC}  200 Mbps:  ~$(estimate_transfer_time "${FILE_SIZE}" 200)"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} Log: ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Reinicia o Zabbix Server se foi parado
if [[ "${SKIP_STOP}" == false ]]; then
    echo ""
    confirm "Reiniciar o Zabbix Server agora?" && {
        log INFO "Reiniciando Zabbix Server no App Server..."
        ssh "${APP_USER}@${APP_SERVER}" 'sudo systemctl start zabbix-server'
        sleep 3
        ZBX_STATUS=$(ssh "${APP_USER}@${APP_SERVER}" 'systemctl is-active zabbix-server 2>/dev/null' || true)
        if [[ "${ZBX_STATUS}" == "active" ]]; then
            log INFO "Zabbix Server reiniciado com sucesso ✓"
        else
            log WARN "Zabbix Server pode não ter reiniciado (status: ${ZBX_STATUS})"
        fi
    } || log WARN "Zabbix Server NÃO foi reiniciado. Lembre-se de reiniciá-lo manualmente."
fi

log INFO "Próximo passo: executar 03-transfer-data.sh para transferir o dump para o Contabo"
log INFO "Script finalizado com sucesso."
