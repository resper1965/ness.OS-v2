#!/usr/bin/env bash
###############################################################################
# 03-transfer-data.sh
#
# Descrição: Transfere o dump do banco de dados do Azure para o Contabo
#            via rsync com compressão, retomada e verificação de checksum.
#
# Execução:  Pode ser executado de qualquer máquina com SSH para ambos.
#
# O que faz:
#   - Transfere via rsync com compressão e progresso
#   - Suporta retomada em caso de interrupção
#   - Verifica checksum MD5 após transferência
#   - Suporta limite de banda
#   - Converte chave PuTTY se necessário
#
# Uso: ./03-transfer-data.sh [--help] [--bwlimit KBPS] [--target-ip IP]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/transfer_$(date +%Y%m%d_%H%M%S).log"

# Servidores (configurável via argumentos ou variáveis de ambiente)
SOURCE_HOST="${SOURCE_HOST:-20.127.231.106}"
SOURCE_USER="${SOURCE_USER:-ness_admin}"
SOURCE_PATH="${SOURCE_PATH:-/backup/zabbix-migration/}"

TARGET_HOST="${TARGET_HOST:-}"  # Deve ser fornecido
TARGET_USER="${TARGET_USER:-ness_admin}"
TARGET_PATH="${TARGET_PATH:-/backup/zabbix-migration/}"

# SSH
SSH_KEY="${SSH_KEY:-${HOME}/.ssh/zabbix_ness}"
SSH_KEY_PUTTY="${SSH_KEY_PUTTY:-${HOME}/.ssh/zabbix_ness.ppk}"
SSH_PORT="${SSH_PORT:-22}"

# Opções de transferência
BWLIMIT=""  # Sem limite por padrão (em KB/s)
DRY_RUN=false

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
    Transfere o dump do banco de dados Zabbix do Azure (origem) para o
    Contabo (destino) via rsync com compressão, retomada e verificação.

${BOLD}OPÇÕES:${NC}
    --help              Exibe esta mensagem de ajuda
    --target-ip IP      IP do servidor Contabo (OBRIGATÓRIO)
    --source-ip IP      IP do servidor Azure (padrão: 20.127.231.106)
    --bwlimit KBPS      Limita banda em KB/s (ex: 50000 = ~50MB/s)
    --ssh-key PATH      Caminho da chave SSH OpenSSH (padrão: ~/.ssh/zabbix_ness)
    --dry-run           Simula transferência sem copiar dados

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    SOURCE_HOST     IP de origem (padrão: 20.127.231.106)
    SOURCE_USER     Usuário SSH origem (padrão: ness_admin)
    SOURCE_PATH     Caminho de origem (padrão: /backup/zabbix-migration/)
    TARGET_HOST     IP de destino (OBRIGATÓRIO)
    TARGET_USER     Usuário SSH destino (padrão: ness_admin)
    TARGET_PATH     Caminho de destino (padrão: /backup/zabbix-migration/)
    SSH_KEY         Chave SSH OpenSSH (padrão: ~/.ssh/zabbix_ness)

${BOLD}MODOS DE TRANSFERÊNCIA:${NC}
    1. Direta (origem → destino):
       Executa rsync via SSH do Azure para o Contabo.
       
    2. Via máquina intermediária:
       Execute o script de uma máquina com acesso a ambos os servidores.

${BOLD}EXEMPLOS:${NC}
    # Transferência básica
    ./${SCRIPT_NAME} --target-ip 203.0.113.50

    # Com limite de banda (50 MB/s)
    ./${SCRIPT_NAME} --target-ip 203.0.113.50 --bwlimit 50000

    # Simulação (dry-run)
    ./${SCRIPT_NAME} --target-ip 203.0.113.50 --dry-run

${BOLD}NOTAS:${NC}
    - A chave SSH deve estar no formato OpenSSH (não PuTTY .ppk)
    - Use --convert-key se só tem a chave .ppk
    - rsync retoma automaticamente transferências interrompidas
    - Seguro para executar múltiplas vezes (idempotente)

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

cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log ERROR "Transferência interrompida com código: ${exit_code}"
        log WARN "Execute o script novamente para retomar a transferência."
        log ERROR "Log: ${LOG_FILE}"
    fi
    exit ${exit_code}
}

trap cleanup EXIT

# Converte chave PuTTY (.ppk) para OpenSSH se necessário
convert_putty_key() {
    if [[ ! -f "${SSH_KEY}" ]] && [[ -f "${SSH_KEY_PUTTY}" ]]; then
        log WARN "Chave OpenSSH não encontrada, mas chave PuTTY existe."
        log INFO "Convertendo chave PuTTY para formato OpenSSH..."
        
        if command -v puttygen &>/dev/null; then
            puttygen "${SSH_KEY_PUTTY}" -O private-openssh -o "${SSH_KEY}"
            chmod 600 "${SSH_KEY}"
            log INFO "Chave convertida com sucesso: ${SSH_KEY} ✓"
        else
            log ERROR "puttygen não encontrado. Instale com: apt install putty-tools"
            log ERROR "Ou converta manualmente: puttygen ${SSH_KEY_PUTTY} -O private-openssh -o ${SSH_KEY}"
            exit 1
        fi
    fi
}

# =============================================================================
# PROCESSAMENTO DE ARGUMENTOS
# =============================================================================
CONVERT_KEY=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            ;;
        --target-ip)
            TARGET_HOST="$2"
            shift 2
            ;;
        --source-ip)
            SOURCE_HOST="$2"
            shift 2
            ;;
        --bwlimit)
            BWLIMIT="$2"
            shift 2
            ;;
        --ssh-key)
            SSH_KEY="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --convert-key)
            CONVERT_KEY=true
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

# Cria diretório de log
mkdir -p "${LOG_DIR}" 2>/dev/null || true

# Verifica se TARGET_HOST foi fornecido
if [[ -z "${TARGET_HOST}" ]]; then
    echo -e "${RED}ERRO: IP do servidor Contabo não informado.${NC}"
    echo "Use: ./${SCRIPT_NAME} --target-ip <IP_CONTABO>"
    exit 1
fi

# Converte chave se necessário
if [[ "${CONVERT_KEY}" == true ]] || [[ ! -f "${SSH_KEY}" ]]; then
    convert_putty_key
fi

# Verifica chave SSH
if [[ ! -f "${SSH_KEY}" ]]; then
    log ERROR "Chave SSH não encontrada: ${SSH_KEY}"
    log ERROR "Use --ssh-key para especificar ou --convert-key para converter da .ppk"
    exit 1
fi

# Verifica rsync
if ! command -v rsync &>/dev/null; then
    log ERROR "rsync não encontrado. Instale com: apt install rsync"
    exit 1
fi

# =============================================================================
# INÍCIO DA EXECUÇÃO
# =============================================================================

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         TRANSFERÊNCIA DE DADOS - AZURE → CONTABO           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Configuração da transferência:"
log INFO "  Origem:  ${SOURCE_USER}@${SOURCE_HOST}:${SOURCE_PATH}"
log INFO "  Destino: ${TARGET_USER}@${TARGET_HOST}:${TARGET_PATH}"
log INFO "  Chave:   ${SSH_KEY}"
[[ -n "${BWLIMIT}" ]] && log INFO "  Limite:  ${BWLIMIT} KB/s"
[[ "${DRY_RUN}" == true ]] && log WARN "  MODO DRY-RUN (simulação)"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Verificar conectividade
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 1/4: Verificando conectividade ═══"

# Testa SSH para origem
log INFO "Testando SSH para origem (${SOURCE_HOST})..."
if ssh -i "${SSH_KEY}" -o ConnectTimeout=10 -o BatchMode=yes \
    -p "${SSH_PORT}" "${SOURCE_USER}@${SOURCE_HOST}" "echo ok" &>/dev/null; then
    log INFO "Conexão com origem OK ✓"
else
    log ERROR "Falha na conexão SSH com ${SOURCE_HOST}"
    exit 1
fi

# Testa SSH para destino
log INFO "Testando SSH para destino (${TARGET_HOST})..."
if ssh -i "${SSH_KEY}" -o ConnectTimeout=10 -o BatchMode=yes \
    -p "${SSH_PORT}" "${TARGET_USER}@${TARGET_HOST}" "echo ok" &>/dev/null; then
    log INFO "Conexão com destino OK ✓"
else
    log ERROR "Falha na conexão SSH com ${TARGET_HOST}"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Verificar arquivos na origem
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 2/4: Verificando arquivos na origem ═══"

# Lista arquivos no diretório de backup
log INFO "Listando arquivos em ${SOURCE_HOST}:${SOURCE_PATH}..."
SOURCE_FILES=$(ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
    "${SOURCE_USER}@${SOURCE_HOST}" \
    "ls -lh ${SOURCE_PATH}*.sql.gz ${SOURCE_PATH}*.md5 2>/dev/null" || true)

if [[ -z "${SOURCE_FILES}" ]]; then
    log ERROR "Nenhum arquivo de dump encontrado em ${SOURCE_HOST}:${SOURCE_PATH}"
    log ERROR "Execute primeiro o script 02-dump-database.sh"
    exit 1
fi

echo "${SOURCE_FILES}" | while read -r line; do
    log INFO "  ${line}"
done

# Calcula tamanho total
TOTAL_SIZE=$(ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
    "${SOURCE_USER}@${SOURCE_HOST}" \
    "du -sb ${SOURCE_PATH} | awk '{print \$1}'" 2>/dev/null || echo "0")

TOTAL_SIZE_HUMAN=$(echo "scale=2; ${TOTAL_SIZE}/1073741824" | bc 2>/dev/null || echo "N/A")
log INFO "Tamanho total a transferir: ~${TOTAL_SIZE_HUMAN} GB"

# Cria diretório de destino
log INFO "Criando diretório de destino no Contabo..."
ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
    "${TARGET_USER}@${TARGET_HOST}" \
    "sudo mkdir -p ${TARGET_PATH} && sudo chown ${TARGET_USER}:${TARGET_USER} ${TARGET_PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Transferir dados via rsync
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 3/4: Transferindo dados ═══"

confirm "Iniciar transferência de ~${TOTAL_SIZE_HUMAN} GB para ${TARGET_HOST}?" || exit 0

# Monta comando rsync
RSYNC_OPTS=(
    -avz                          # Archive, verbose, compress
    --progress                     # Mostra progresso
    --partial                      # Mantém arquivos parciais para retomada
    --partial-dir=".rsync-partial" # Diretório para parciais
    --stats                        # Mostra estatísticas
    --human-readable               # Tamanhos legíveis
    -e "ssh -i ${SSH_KEY} -p ${SSH_PORT} -o StrictHostKeyChecking=no"
)

# Adiciona limite de banda se especificado
if [[ -n "${BWLIMIT}" ]]; then
    RSYNC_OPTS+=(--bwlimit="${BWLIMIT}")
fi

# Adiciona dry-run se especificado
if [[ "${DRY_RUN}" == true ]]; then
    RSYNC_OPTS+=(--dry-run)
    log WARN "MODO DRY-RUN: nenhum dado será transferido"
fi

TRANSFER_START=$(date +%s)

log INFO "Executando rsync..."
log INFO "Comando: rsync ${RSYNC_OPTS[*]} ${SOURCE_USER}@${SOURCE_HOST}:${SOURCE_PATH} ${TARGET_USER}@${TARGET_HOST}:${TARGET_PATH}"

# Executa rsync (origem → destino, através desta máquina)
# Se executando NA origem, pode fazer rsync direto para o destino
rsync "${RSYNC_OPTS[@]}" \
    "${SOURCE_USER}@${SOURCE_HOST}:${SOURCE_PATH}" \
    "${TARGET_USER}@${TARGET_HOST}:${TARGET_PATH}" \
    2>&1 | tee -a "${LOG_FILE}"

TRANSFER_END=$(date +%s)
TRANSFER_DURATION=$((TRANSFER_END - TRANSFER_START))

log INFO "Transferência concluída ✓"
log INFO "Duração: $((TRANSFER_DURATION / 3600))h $((TRANSFER_DURATION % 3600 / 60))m $((TRANSFER_DURATION % 60))s"

if [[ ${TOTAL_SIZE} -gt 0 ]] && [[ ${TRANSFER_DURATION} -gt 0 ]]; then
    SPEED_MBPS=$(echo "scale=2; ${TOTAL_SIZE} * 8 / ${TRANSFER_DURATION} / 1000000" | bc 2>/dev/null || echo "N/A")
    log INFO "Velocidade média: ${SPEED_MBPS} Mbps"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Verificar checksums
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 4/4: Verificando checksums ═══"

if [[ "${DRY_RUN}" == true ]]; then
    log WARN "Dry-run: pulando verificação de checksum."
else
    # Obtém checksums da origem
    log INFO "Obtendo checksums da origem..."
    SOURCE_MD5=$(ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
        "${SOURCE_USER}@${SOURCE_HOST}" \
        "cat ${SOURCE_PATH}*.md5 2>/dev/null" || echo "")
    
    if [[ -z "${SOURCE_MD5}" ]]; then
        log WARN "Nenhum arquivo .md5 encontrado na origem."
        log WARN "Calculando checksum na origem (pode demorar)..."
        SOURCE_MD5=$(ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
            "${SOURCE_USER}@${SOURCE_HOST}" \
            "cd ${SOURCE_PATH} && md5sum *.sql.gz 2>/dev/null" || echo "")
    fi
    
    # Obtém checksums do destino
    log INFO "Calculando checksums no destino..."
    TARGET_MD5=$(ssh -i "${SSH_KEY}" -p "${SSH_PORT}" \
        "${TARGET_USER}@${TARGET_HOST}" \
        "cd ${TARGET_PATH} && md5sum *.sql.gz 2>/dev/null" || echo "")
    
    # Compara
    if [[ -n "${SOURCE_MD5}" ]] && [[ -n "${TARGET_MD5}" ]]; then
        SOURCE_HASH=$(echo "${SOURCE_MD5}" | awk '{print $1}' | sort)
        TARGET_HASH=$(echo "${TARGET_MD5}" | awk '{print $1}' | sort)
        
        if [[ "${SOURCE_HASH}" == "${TARGET_HASH}" ]]; then
            log INFO "Checksums conferem ✓"
            echo -e "  ${GREEN}Origem:  ${SOURCE_MD5}${NC}"
            echo -e "  ${GREEN}Destino: ${TARGET_MD5}${NC}"
        else
            log ERROR "CHECKSUMS NÃO CONFEREM!"
            echo -e "  ${RED}Origem:  ${SOURCE_MD5}${NC}"
            echo -e "  ${RED}Destino: ${TARGET_MD5}${NC}"
            log ERROR "A transferência pode estar corrompida. Execute novamente."
            exit 1
        fi
    else
        log WARN "Não foi possível verificar checksums automaticamente."
        log WARN "Verifique manualmente os hashes MD5."
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# RESUMO
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                RESUMO DA TRANSFERÊNCIA                     ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} Origem:       ${CYAN}${SOURCE_HOST}:${SOURCE_PATH}${NC}"
echo -e "${BOLD}║${NC} Destino:      ${CYAN}${TARGET_HOST}:${TARGET_PATH}${NC}"
echo -e "${BOLD}║${NC} Tamanho:      ${CYAN}~${TOTAL_SIZE_HUMAN} GB${NC}"
echo -e "${BOLD}║${NC} Duração:      ${CYAN}$((TRANSFER_DURATION / 3600))h $((TRANSFER_DURATION % 3600 / 60))m $((TRANSFER_DURATION % 60))s${NC}"
echo -e "${BOLD}║${NC} Checksum:     ${GREEN}OK ✓${NC}"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} Log: ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Próximo passo: executar 04-import-database.sh no servidor Contabo"
log INFO "Script finalizado com sucesso."
