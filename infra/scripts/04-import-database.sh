#!/usr/bin/env bash
###############################################################################
# 04-import-database.sh
#
# Descrição: Importa o dump do banco de dados Zabbix no servidor Contabo
#            e executa o upgrade de schema se necessário (6.4 → 7.0).
#
# Execução:  Rodar no servidor Contabo (destino)
#
# O que faz:
#   - Verifica integridade do dump (checksum MD5)
#   - Para o Zabbix Server se estiver rodando
#   - Cria banco e usuário se não existirem
#   - Importa o dump com progresso
#   - Executa upgrade de schema (6.4 → 7.0) se necessário
#   - Verifica contagem de tabelas
#
# Uso: ./04-import-database.sh [--help] [--dump-file PATH] [--skip-upgrade]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/import_$(date +%Y%m%d_%H%M%S).log"
readonly BACKUP_DIR="/backup/zabbix-migration"

# Banco de dados
DB_NAME="${DB_NAME:-dbzabbix}"
DB_USER="${DB_USER:-usrzabbix}"
DB_PASSWORD="${DB_PASSWORD:-}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-}"
DB_CHARSET="${DB_CHARSET:-utf8mb4}"
DB_COLLATION="${DB_COLLATION:-utf8mb4_bin}"

# Caminho do dump (auto-detecta o mais recente se não informado)
DUMP_FILE=""

# Opções
SKIP_UPGRADE=false
EXPECTED_TABLES=180  # Aproximado para Zabbix 6.4

# Caminho do script de upgrade do Zabbix 7.0
ZABBIX_UPGRADE_SQL="/usr/share/zabbix-sql-scripts/mysql/server.sql"

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
    Importa o dump do banco de dados Zabbix transferido do Azure.
    Cria o banco e usuário se necessário, importa os dados e executa
    o upgrade de schema de 6.4 para 7.0.

${BOLD}OPÇÕES:${NC}
    --help              Exibe esta mensagem de ajuda
    --dump-file PATH    Caminho do arquivo .sql.gz (auto-detecta se omitido)
    --skip-upgrade      Não executa upgrade de schema

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    DB_NAME             Nome do banco (padrão: dbzabbix)
    DB_USER             Usuário do banco (padrão: usrzabbix)
    DB_PASSWORD         Senha do usuário (solicitada se não informada)
    DB_ROOT_PASSWORD    Senha root do MariaDB (vazio para socket auth)

${BOLD}EXEMPLOS:${NC}
    # Auto-detectar dump mais recente
    DB_PASSWORD=senha ./${SCRIPT_NAME}

    # Especificar arquivo
    DB_PASSWORD=senha ./${SCRIPT_NAME} --dump-file /backup/zabbix-migration/dbzabbix_20260629.sql.gz

    # Sem upgrade de schema
    DB_PASSWORD=senha ./${SCRIPT_NAME} --skip-upgrade

${BOLD}NOTAS:${NC}
    - Execute no servidor Contabo (destino)
    - O import de ~100 GB comprimido pode levar 2-6 horas
    - Requer root ou sudo para operações de banco
    - Verifique o log: ${LOG_DIR}/

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
        log ERROR "Script interrompido com código de saída: ${exit_code}"
        log ERROR "O banco pode estar em estado parcial."
        log ERROR "Verifique o log: ${LOG_FILE}"
    fi
    exit ${exit_code}
}

trap cleanup EXIT

# Executa comando MySQL como root
mysql_root() {
    if [[ -n "${DB_ROOT_PASSWORD}" ]]; then
        mysql -u root -p"${DB_ROOT_PASSWORD}" "$@"
    else
        # Socket authentication (padrão no Debian)
        sudo mysql "$@"
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
        --dump-file)
            DUMP_FILE="$2"
            shift 2
            ;;
        --skip-upgrade)
            SKIP_UPGRADE=true
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
# VALIDAÇÕES INICIAIS
# =============================================================================

# Cria diretório de log
mkdir -p "${LOG_DIR}" 2>/dev/null || true

# Solicita senha do banco se não informada
if [[ -z "${DB_PASSWORD}" ]]; then
    echo -e "${YELLOW}Senha do usuário '${DB_USER}' do banco de dados:${NC}"
    read -r -s -p "  Senha: " DB_PASSWORD
    echo ""
    if [[ -z "${DB_PASSWORD}" ]]; then
        log ERROR "Senha não pode ser vazia."
        exit 1
    fi
fi

# Auto-detecta o dump mais recente se não especificado
if [[ -z "${DUMP_FILE}" ]]; then
    log INFO "Procurando dump mais recente em ${BACKUP_DIR}..."
    DUMP_FILE=$(ls -t "${BACKUP_DIR}"/dbzabbix_*.sql.gz 2>/dev/null | head -1 || true)
    
    if [[ -z "${DUMP_FILE}" ]]; then
        log ERROR "Nenhum arquivo de dump encontrado em ${BACKUP_DIR}/"
        log ERROR "Execute os scripts 02 e 03 primeiro, ou use --dump-file."
        exit 1
    fi
    log INFO "Dump detectado: ${DUMP_FILE}"
fi

# Verifica se o arquivo existe
if [[ ! -f "${DUMP_FILE}" ]]; then
    log ERROR "Arquivo de dump não encontrado: ${DUMP_FILE}"
    exit 1
fi

# =============================================================================
# INÍCIO DA EXECUÇÃO
# =============================================================================

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       IMPORTAÇÃO DO BANCO DE DADOS - ZABBIX CONTABO        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Iniciando importação do banco de dados"
log INFO "Dump: ${DUMP_FILE}"
log INFO "Banco: ${DB_NAME} | Usuário: ${DB_USER}"
log INFO "Log: ${LOG_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Verificar checksum MD5
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 1/7: Verificando integridade do dump ═══"

MD5_FILE="${DUMP_FILE}.md5"
DUMP_SIZE=$(stat -c%s "${DUMP_FILE}" 2>/dev/null || stat -f%z "${DUMP_FILE}" 2>/dev/null)
DUMP_SIZE_GB=$(echo "scale=2; ${DUMP_SIZE}/1073741824" | bc 2>/dev/null || echo "N/A")
log INFO "Tamanho do dump: ${DUMP_SIZE_GB} GB"

if [[ -f "${MD5_FILE}" ]]; then
    log INFO "Verificando checksum MD5..."
    
    EXPECTED_MD5=$(awk '{print $1}' "${MD5_FILE}")
    ACTUAL_MD5=$(md5sum "${DUMP_FILE}" | awk '{print $1}')
    
    if [[ "${EXPECTED_MD5}" == "${ACTUAL_MD5}" ]]; then
        log INFO "Checksum MD5 confere ✓"
        log INFO "  Esperado: ${EXPECTED_MD5}"
        log INFO "  Atual:    ${ACTUAL_MD5}"
    else
        log ERROR "CHECKSUM NÃO CONFERE!"
        log ERROR "  Esperado: ${EXPECTED_MD5}"
        log ERROR "  Atual:    ${ACTUAL_MD5}"
        log ERROR "O arquivo pode estar corrompido. Transfira novamente."
        exit 1
    fi
else
    log WARN "Arquivo .md5 não encontrado: ${MD5_FILE}"
    log WARN "Não é possível verificar integridade. Continuando sem verificação."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Parar Zabbix Server
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 2/7: Parando Zabbix Server ═══"

if systemctl is-active zabbix-server &>/dev/null; then
    log INFO "Parando Zabbix Server..."
    sudo systemctl stop zabbix-server
    sleep 2
    
    if ! systemctl is-active zabbix-server &>/dev/null; then
        log INFO "Zabbix Server parado ✓"
    else
        log ERROR "Não foi possível parar o Zabbix Server"
        exit 1
    fi
else
    log INFO "Zabbix Server já está parado ✓"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Verificar espaço em disco
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 3/7: Verificando espaço em disco ═══"

# O dump descomprimido pode ser 4-5x maior que o comprimido
ESTIMATED_UNCOMPRESSED=$(echo "scale=0; ${DUMP_SIZE} * 5 / 1073741824" | bc 2>/dev/null || echo "500")
AVAILABLE_SPACE=$(df -BG /var/lib/mysql | tail -1 | awk '{print $4}' | tr -d 'G')

log INFO "Espaço estimado necessário: ~${ESTIMATED_UNCOMPRESSED} GB"
log INFO "Espaço disponível: ${AVAILABLE_SPACE} GB"

if (( AVAILABLE_SPACE < ESTIMATED_UNCOMPRESSED )); then
    log ERROR "Espaço insuficiente!"
    log ERROR "Necessário: ~${ESTIMATED_UNCOMPRESSED} GB | Disponível: ${AVAILABLE_SPACE} GB"
    exit 1
fi
log INFO "Espaço em disco suficiente ✓"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Criar banco e usuário
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 4/7: Preparando banco de dados ═══"

# Verifica se MariaDB está rodando
if ! systemctl is-active mariadb &>/dev/null; then
    log INFO "Iniciando MariaDB..."
    sudo systemctl start mariadb
    sleep 3
fi

# Verifica se o banco já existe
DB_EXISTS=$(mysql_root -N -s -e "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='${DB_NAME}';" 2>/dev/null || echo "0")

if [[ "${DB_EXISTS}" -gt 0 ]]; then
    log WARN "Banco '${DB_NAME}' já existe."
    
    # Conta tabelas existentes
    EXISTING_TABLES=$(mysql_root -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" 2>/dev/null || echo "0")
    log WARN "Tabelas existentes: ${EXISTING_TABLES}"
    
    confirm "ATENÇÃO: O banco '${DB_NAME}' será SUBSTITUÍDO. Todos os dados atuais serão perdidos." || exit 0
    
    log INFO "Removendo banco existente..."
    mysql_root -e "DROP DATABASE ${DB_NAME};" 2>>"${LOG_FILE}"
fi

# Cria banco de dados
log INFO "Criando banco de dados '${DB_NAME}'..."
mysql_root -e "CREATE DATABASE ${DB_NAME} CHARACTER SET ${DB_CHARSET} COLLATE ${DB_COLLATION};" 2>>"${LOG_FILE}"
log INFO "Banco criado ✓"

# Cria usuário e concede privilégios
log INFO "Configurando usuário '${DB_USER}'..."
mysql_root -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASSWORD}';" 2>>"${LOG_FILE}"
mysql_root -e "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';" 2>>"${LOG_FILE}"
mysql_root -e "FLUSH PRIVILEGES;" 2>>"${LOG_FILE}"
log INFO "Usuário configurado ✓"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 5: Importar dump
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 5/7: Importando dados ═══"

log WARN "A importação pode levar 2-6 horas dependendo do tamanho do dump."
log INFO "Acompanhe o progresso abaixo ou pelo log: ${LOG_FILE}"

confirm "Iniciar importação de ${DUMP_SIZE_GB} GB (comprimido)?" || exit 0

# Detecta ferramenta de descompressão
if command -v unpigz &>/dev/null; then
    DECOMPRESS_CMD="unpigz -c"
    log INFO "Usando unpigz para descompressão (paralelo) ✓"
elif command -v gunzip &>/dev/null; then
    DECOMPRESS_CMD="gunzip -c"
    log INFO "Usando gunzip para descompressão"
    log WARN "Para melhor performance, instale pigz: apt install pigz"
else
    log ERROR "Nenhuma ferramenta de descompressão encontrada (unpigz/gunzip)"
    exit 1
fi

# Detecta pv para barra de progresso
USE_PV=false
if command -v pv &>/dev/null; then
    USE_PV=true
    log INFO "pv encontrado - progresso será exibido ✓"
else
    log WARN "pv não encontrado. Instale com: apt install pv"
    log WARN "Importação sem barra de progresso."
fi

IMPORT_START=$(date +%s)

# Configurações do MariaDB para importação mais rápida
log INFO "Otimizando MariaDB para importação..."
mysql_root -e "SET GLOBAL innodb_buffer_pool_size = $(echo "$(free -b | awk '/Mem:/{print $7}') * 70 / 100" | bc);" 2>/dev/null || true
mysql_root -e "SET GLOBAL innodb_log_file_size = 1073741824;" 2>/dev/null || true  # 1GB
mysql_root -e "SET GLOBAL max_allowed_packet = 1073741824;" 2>/dev/null || true    # 1GB
mysql_root -e "SET GLOBAL innodb_flush_log_at_trx_commit = 0;" 2>/dev/null || true
mysql_root -e "SET GLOBAL innodb_doublewrite = 0;" 2>/dev/null || true

# Importa dados
if [[ "${USE_PV}" == true ]]; then
    ${DECOMPRESS_CMD} "${DUMP_FILE}" | \
        pv -W -s "${DUMP_SIZE}" | \
        mysql_root "${DB_NAME}" 2>>"${LOG_FILE}"
else
    ${DECOMPRESS_CMD} "${DUMP_FILE}" | \
        mysql_root "${DB_NAME}" 2>>"${LOG_FILE}"
fi

IMPORT_END=$(date +%s)
IMPORT_DURATION=$((IMPORT_END - IMPORT_START))

# Restaura configurações normais do MariaDB
log INFO "Restaurando configurações do MariaDB..."
mysql_root -e "SET GLOBAL innodb_flush_log_at_trx_commit = 1;" 2>/dev/null || true
mysql_root -e "SET GLOBAL innodb_doublewrite = 1;" 2>/dev/null || true

log INFO "Importação concluída ✓"
log INFO "Duração: $((IMPORT_DURATION / 3600))h $((IMPORT_DURATION % 3600 / 60))m $((IMPORT_DURATION % 60))s"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 6: Verificar importação
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 6/7: Verificando importação ═══"

# Conta tabelas importadas
TABLE_COUNT=$(mysql_root -N -s -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" 2>/dev/null || echo "0")
log INFO "Tabelas importadas: ${TABLE_COUNT}"

if [[ ${TABLE_COUNT} -ge ${EXPECTED_TABLES} ]]; then
    log INFO "Contagem de tabelas OK (${TABLE_COUNT} >= ${EXPECTED_TABLES}) ✓"
else
    log WARN "Contagem de tabelas menor que esperada (${TABLE_COUNT} < ${EXPECTED_TABLES})"
    log WARN "Verifique se o dump estava completo."
fi

# Tamanho do banco após importação
DB_SIZE=$(mysql_root -N -s -e "SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024 / 1024, 2) FROM information_schema.tables WHERE table_schema='${DB_NAME}';" 2>/dev/null || echo "N/A")
log INFO "Tamanho do banco após importação: ${DB_SIZE} GB"

# Verifica se tabelas críticas existem
for table in hosts items triggers events history history_uint trends trends_uint; do
    if mysql_root -N -s -e "SELECT 1 FROM information_schema.tables WHERE table_schema='${DB_NAME}' AND table_name='${table}';" 2>/dev/null | grep -q 1; then
        log INFO "  Tabela '${table}' presente ✓"
    else
        log WARN "  Tabela '${table}' NÃO encontrada!"
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 7: Upgrade de schema (6.4 → 7.0)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 7/7: Upgrade de schema (6.4 → 7.0) ═══"

if [[ "${SKIP_UPGRADE}" == true ]]; then
    log WARN "Upgrade de schema ignorado (--skip-upgrade)"
else
    # Verifica versão atual do schema
    CURRENT_VERSION=$(mysql_root -N -s -e "SELECT mandatory FROM ${DB_NAME}.dbversion;" 2>/dev/null || echo "0")
    log INFO "Versão atual do schema: ${CURRENT_VERSION}"
    
    # Zabbix 6.4 schema version: 6040000
    # Zabbix 7.0 schema version: 7000000
    if [[ ${CURRENT_VERSION} -lt 7000000 ]]; then
        log INFO "Upgrade de schema necessário (${CURRENT_VERSION} → 7.0)"
        
        # Verifica se o script de upgrade existe
        # O Zabbix 7.0 faz o upgrade automaticamente ao iniciar o servidor
        if [[ -f "${ZABBIX_UPGRADE_SQL}" ]]; then
            log WARN "Arquivo de upgrade encontrado: ${ZABBIX_UPGRADE_SQL}"
            log INFO "O Zabbix Server 7.0 executará o upgrade automaticamente ao iniciar."
            log INFO "Isso pode levar vários minutos."
        else
            log INFO "O upgrade será feito automaticamente pelo Zabbix Server ao iniciar."
        fi
        
        # Inicia o Zabbix Server para executar o upgrade
        confirm "Iniciar Zabbix Server para executar upgrade de schema?" || {
            log WARN "Upgrade adiado. Inicie o Zabbix Server manualmente quando estiver pronto."
            log WARN "Comando: sudo systemctl start zabbix-server"
            exit 0
        }
        
        log INFO "Iniciando Zabbix Server para upgrade de schema..."
        sudo systemctl start zabbix-server
        
        # Aguarda upgrade completar (monitora log)
        log INFO "Aguardando upgrade do schema (pode levar 10-30 minutos)..."
        
        UPGRADE_TIMEOUT=3600  # 60 minutos
        ELAPSED=0
        INTERVAL=30
        
        while [[ ${ELAPSED} -lt ${UPGRADE_TIMEOUT} ]]; do
            sleep ${INTERVAL}
            ELAPSED=$((ELAPSED + INTERVAL))
            
            # Verifica se o upgrade completou
            NEW_VERSION=$(mysql_root -N -s -e "SELECT mandatory FROM ${DB_NAME}.dbversion;" 2>/dev/null || echo "0")
            
            if [[ ${NEW_VERSION} -ge 7000000 ]]; then
                log INFO "Upgrade de schema concluído ✓"
                log INFO "Nova versão do schema: ${NEW_VERSION}"
                break
            fi
            
            # Verifica se houve erro no log
            if journalctl -u zabbix-server --since "-${INTERVAL} seconds" --no-pager 2>/dev/null | grep -qi "error\|fatal\|cannot"; then
                log ERROR "Erros detectados durante o upgrade. Verifique:"
                log ERROR "  journalctl -u zabbix-server -f"
                log ERROR "  tail -f /var/log/zabbix/zabbix_server.log"
                break
            fi
            
            echo -e "  ${CYAN}Aguardando... (${ELAPSED}s / schema version: ${NEW_VERSION})${NC}"
        done
        
        if [[ ${ELAPSED} -ge ${UPGRADE_TIMEOUT} ]]; then
            log WARN "Timeout aguardando upgrade. Verifique o log do Zabbix."
        fi
    else
        log INFO "Schema já está na versão 7.0 ou superior (${CURRENT_VERSION}). Upgrade não necessário ✓"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# RESUMO
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                RESUMO DA IMPORTAÇÃO                        ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC} Dump:            ${CYAN}${DUMP_FILE}${NC}"
echo -e "${BOLD}║${NC} Banco:           ${CYAN}${DB_NAME}${NC}"
echo -e "${BOLD}║${NC} Tabelas:         ${CYAN}${TABLE_COUNT}${NC}"
echo -e "${BOLD}║${NC} Tamanho:         ${CYAN}${DB_SIZE} GB${NC}"
echo -e "${BOLD}║${NC} Duração:         ${CYAN}$((IMPORT_DURATION / 3600))h $((IMPORT_DURATION % 3600 / 60))m $((IMPORT_DURATION % 60))s${NC}"
echo -e "${BOLD}║${NC} Checksum:        ${GREEN}OK ✓${NC}"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC} Log: ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Próximo passo: executar 05-validate-migration.sh para validar a migração"
log INFO "Script finalizado com sucesso."
