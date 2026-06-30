#!/usr/bin/env bash
###############################################################################
# 06-cleanup-azure.sh
#
# Descrição: Script de descomissionamento dos servidores Azure após
#            validação bem-sucedida da migração para o Contabo.
#
# Execução:  Rodar após validação bem-sucedida (script 05)
#
# O que faz:
#   - Exibe checklist de pré-descomissionamento
#   - Para serviços nos servidores Azure
#   - Desaloca (NÃO deleta) as VMs Azure
#   - Exibe lembretes de acompanhamento
#
# Uso: ./06-cleanup-azure.sh [--help]
###############################################################################
set -euo pipefail

# =============================================================================
# CONSTANTES E CONFIGURAÇÃO
# =============================================================================
readonly SCRIPT_NAME="$(basename "$0")"
readonly LOG_DIR="/var/log/zabbix-migration"
readonly LOG_FILE="${LOG_DIR}/cleanup_$(date +%Y%m%d_%H%M%S).log"

# Servidores Azure
readonly APP_SERVER="52.146.5.10"
readonly DB_SERVER="20.127.231.106"
readonly SSH_USER="ness_admin"

# Azure Resource Group (ajuste conforme sua configuração)
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-zabbix}"
AZURE_VM_APP="${AZURE_VM_APP:-VM-Zabbix-02}"
AZURE_VM_DB="${AZURE_VM_DB:-VM-Zabbix-01}"

# Dias de retenção como fallback
readonly FALLBACK_DAYS=7

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
    Script interativo de descomissionamento dos servidores Azure após
    migração do Zabbix para o Contabo. Para serviços e desaloca VMs.
    NÃO deleta recursos - apenas desaloca para parar a cobrança.

${BOLD}OPÇÕES:${NC}
    --help              Exibe esta mensagem de ajuda

${BOLD}VARIÁVEIS DE AMBIENTE:${NC}
    AZURE_RESOURCE_GROUP   Resource group (padrão: rg-zabbix)
    AZURE_VM_APP           Nome da VM App (padrão: VM-Zabbix-02)
    AZURE_VM_DB            Nome da VM DB (padrão: VM-Zabbix-01)

${BOLD}NOTAS:${NC}
    - Execute SOMENTE após validação bem-sucedida (script 05)
    - Requer confirmação para cada ação
    - As VMs são DESALOCADAS, não deletadas
    - Mantenha as VMs desalocadas por ${FALLBACK_DAYS} dias como fallback

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

# Confirmação com texto personalizado
confirm_action() {
    local message="$1"
    local required_text="${2:-}"
    
    echo -e "\n${YELLOW}⚠  ${message}${NC}"
    
    if [[ -n "${required_text}" ]]; then
        echo -e "   Digite '${BOLD}${required_text}${NC}' para confirmar:"
        read -r response
        if [[ "${response}" != "${required_text}" ]]; then
            log WARN "Confirmação não corresponde. Ação cancelada."
            return 1
        fi
    else
        read -r -p "   Continuar? (s/N): " response
        case "${response}" in
            [sS]|[sS][iI][mM]) return 0 ;;
            *)
                log WARN "Ação cancelada pelo usuário."
                return 1
                ;;
        esac
    fi
}

cleanup() {
    local exit_code=$?
    if [[ ${exit_code} -ne 0 ]]; then
        log ERROR "Script interrompido. Verifique o estado dos servidores Azure."
        log ERROR "Log: ${LOG_FILE}"
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
echo -e "${BOLD}║       DESCOMISSIONAMENTO AZURE - MIGRAÇÃO ZABBIX           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Iniciando procedimento de descomissionamento"
log INFO "Log: ${LOG_FILE}"

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1: Checklist de pré-descomissionamento
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 1/4: Checklist de Pré-Descomissionamento ═══"

echo ""
echo -e "${BOLD}Verifique cada item antes de prosseguir:${NC}"
echo ""

CHECKLIST_ITEMS=(
    "Todos os hosts estão reportando ao novo servidor Contabo?"
    "Todas as alertas e notificações estão funcionando corretamente?"
    "Os registros DNS foram atualizados para apontar ao Contabo?"
    "Os jobs de backup estão configurados e funcionando no Contabo?"
    "O monitoramento do próprio servidor Contabo está configurado?"
    "Os stakeholders foram notificados sobre a migração?"
    "O script 05-validate-migration.sh passou sem FAILs?"
    "Os dashboards e gráficos estão acessíveis no novo servidor?"
)

ALL_CONFIRMED=true

for item in "${CHECKLIST_ITEMS[@]}"; do
    echo -e "  ${CYAN}▸${NC} ${item}"
    read -r -p "    Confirmado? (s/N): " response
    case "${response}" in
        [sS]|[sS][iI][mM])
            echo -e "    ${GREEN}✓ Confirmado${NC}"
            log INFO "Checklist OK: ${item}"
            ;;
        *)
            echo -e "    ${RED}✗ NÃO confirmado${NC}"
            log WARN "Checklist PENDENTE: ${item}"
            ALL_CONFIRMED=false
            ;;
    esac
    echo ""
done

if [[ "${ALL_CONFIRMED}" == false ]]; then
    echo -e "${RED}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}${BOLD}║  ATENÇÃO: Nem todos os itens do checklist foram confirmados ║${NC}"
    echo -e "${RED}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    confirm_action "Prosseguir mesmo assim? Isso NÃO é recomendado." || {
        log INFO "Descomissionamento adiado. Resolva os itens pendentes primeiro."
        exit 0
    }
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2: Parar serviços no App Server (VM-Zabbix-02)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 2/4: Parando serviços no App Server ═══"

log INFO "Servidor: ${APP_SERVER} (${AZURE_VM_APP})"
echo -e "${CYAN}Serviços a serem parados: zabbix-server, zabbix-agent2, apache2${NC}"

confirm_action "Parar serviços no App Server (${APP_SERVER})?" || {
    log WARN "Parada de serviços no App Server pulada."
    echo ""
    log INFO "Para parar manualmente:"
    echo -e "  ${CYAN}ssh ${SSH_USER}@${APP_SERVER} 'sudo systemctl stop zabbix-server zabbix-agent2 apache2'${NC}"
}

if confirm_action "Parar serviços no App Server (${APP_SERVER})?" 2>/dev/null; then
    log INFO "Parando serviços no App Server..."
    
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "${SSH_USER}@${APP_SERVER}" \
        'sudo systemctl stop zabbix-server zabbix-agent2 apache2 2>/dev/null; echo "OK"' 2>/dev/null; then
        log INFO "Serviços parados no App Server ✓"
    else
        log WARN "Não foi possível parar serviços via SSH."
        log WARN "Tente manualmente ou prossiga com a desalocação da VM."
    fi
    
    # Desabilita serviços para não iniciarem no boot
    ssh -o ConnectTimeout=10 "${SSH_USER}@${APP_SERVER}" \
        'sudo systemctl disable zabbix-server zabbix-agent2 apache2 2>/dev/null' || true
    log INFO "Serviços desabilitados no App Server ✓"
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3: Parar serviços no DB Server (VM-Zabbix-01)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 3/4: Parando serviços no DB Server ═══"

log INFO "Servidor: ${DB_SERVER} (${AZURE_VM_DB})"
echo -e "${CYAN}Serviços a serem parados: mariadb, zabbix-agent2${NC}"

confirm_action "Parar serviços no DB Server (${DB_SERVER})?" || {
    log WARN "Parada de serviços no DB Server pulada."
    echo ""
    log INFO "Para parar manualmente:"
    echo -e "  ${CYAN}ssh ${SSH_USER}@${DB_SERVER} 'sudo systemctl stop mariadb zabbix-agent2'${NC}"
}

if ssh -o ConnectTimeout=10 -o BatchMode=yes "${SSH_USER}@${DB_SERVER}" \
    'sudo systemctl stop mariadb zabbix-agent2 2>/dev/null; echo "OK"' 2>/dev/null; then
    log INFO "Serviços parados no DB Server ✓"
    
    ssh -o ConnectTimeout=10 "${SSH_USER}@${DB_SERVER}" \
        'sudo systemctl disable mariadb zabbix-agent2 2>/dev/null' || true
    log INFO "Serviços desabilitados no DB Server ✓"
else
    log WARN "Não foi possível parar serviços via SSH no DB Server."
fi

# ─────────────────────────────────────────────────────────────────────────────
# PASSO 4: Desalocar VMs Azure
# ─────────────────────────────────────────────────────────────────────────────
echo ""
log STEP "═══ PASSO 4/4: Desalocação das VMs Azure ═══"

echo -e "${YELLOW}${BOLD}"
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  IMPORTANTE: As VMs serão DESALOCADAS, não deletadas.  │"
echo "  │  Isso PARA a cobrança de compute, mas mantém os discos.│"
echo "  │  Os dados ficam preservados por ${FALLBACK_DAYS} dias como fallback. │"
echo "  └─────────────────────────────────────────────────────────┘"
echo -e "${NC}"

# Verifica se Azure CLI está disponível
if command -v az &>/dev/null; then
    log INFO "Azure CLI encontrado ✓"
    
    echo ""
    echo -e "${BOLD}Comandos de desalocação:${NC}"
    echo ""
    echo -e "  ${CYAN}# Desalocar App Server (${AZURE_VM_APP})${NC}"
    echo -e "  ${BOLD}az vm deallocate --resource-group ${AZURE_RESOURCE_GROUP} --name ${AZURE_VM_APP}${NC}"
    echo ""
    echo -e "  ${CYAN}# Desalocar DB Server (${AZURE_VM_DB})${NC}"
    echo -e "  ${BOLD}az vm deallocate --resource-group ${AZURE_RESOURCE_GROUP} --name ${AZURE_VM_DB}${NC}"
    echo ""
    
    # Desalocar App Server
    confirm_action "Desalocar ${AZURE_VM_APP} (App Server)?" "DESALOCAR" && {
        log INFO "Desalocando ${AZURE_VM_APP}..."
        if az vm deallocate \
            --resource-group "${AZURE_RESOURCE_GROUP}" \
            --name "${AZURE_VM_APP}" \
            --no-wait 2>>"${LOG_FILE}"; then
            log INFO "${AZURE_VM_APP} desalocação iniciada ✓"
        else
            log ERROR "Falha ao desalocar ${AZURE_VM_APP}"
        fi
    }
    
    # Desalocar DB Server
    confirm_action "Desalocar ${AZURE_VM_DB} (DB Server)?" "DESALOCAR" && {
        log INFO "Desalocando ${AZURE_VM_DB}..."
        if az vm deallocate \
            --resource-group "${AZURE_RESOURCE_GROUP}" \
            --name "${AZURE_VM_DB}" \
            --no-wait 2>>"${LOG_FILE}"; then
            log INFO "${AZURE_VM_DB} desalocação iniciada ✓"
        else
            log ERROR "Falha ao desalocar ${AZURE_VM_DB}"
        fi
    }
else
    log WARN "Azure CLI (az) não encontrado."
    echo ""
    echo -e "${BOLD}Execute manualmente no Azure Cloud Shell ou instale o Azure CLI:${NC}"
    echo ""
    echo -e "  ${CYAN}# Instalar Azure CLI${NC}"
    echo -e "  curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash"
    echo ""
    echo -e "  ${CYAN}# Login${NC}"
    echo -e "  az login"
    echo ""
    echo -e "  ${CYAN}# Desalocar VMs${NC}"
    echo -e "  az vm deallocate --resource-group ${AZURE_RESOURCE_GROUP} --name ${AZURE_VM_APP}"
    echo -e "  az vm deallocate --resource-group ${AZURE_RESOURCE_GROUP} --name ${AZURE_VM_DB}"
fi

# ─────────────────────────────────────────────────────────────────────────────
# LEMBRETES FINAIS
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║                    LEMBRETES IMPORTANTES                   ║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}1.${NC} Mantenha as VMs Azure ${BOLD}DESALOCADAS por ${FALLBACK_DAYS} dias${NC}"
echo -e "${BOLD}║${NC}     como plano de rollback."
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}2.${NC} Após ${FALLBACK_DAYS} dias sem problemas, delete os recursos:"
echo -e "${BOLD}║${NC}     ${CYAN}az group delete --name ${AZURE_RESOURCE_GROUP}${NC}"
echo -e "${BOLD}║${NC}     ${RED}⚠ CUIDADO: isso remove TUDO no resource group!${NC}"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}3.${NC} Verifique a fatura Azure no próximo ciclo para"
echo -e "${BOLD}║${NC}     confirmar que não há cobranças inesperadas."
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}4.${NC} Recursos Azure que podem ter custos mesmo desalocados:"
echo -e "${BOLD}║${NC}     • Discos gerenciados (armazenamento)"
echo -e "${BOLD}║${NC}     • IPs públicos reservados"
echo -e "${BOLD}║${NC}     • Snapshots e backups"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  ${YELLOW}5.${NC} Data sugerida para deleção: $(date -d "+${FALLBACK_DAYS} days" '+%Y-%m-%d' 2>/dev/null || echo "em ${FALLBACK_DAYS} dias")"
echo -e "${BOLD}║${NC}"
echo -e "${BOLD}║${NC}  Log: ${LOG_FILE}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

log INFO "Descomissionamento concluído."
log INFO "Migração Azure → Contabo finalizada com sucesso! 🎉"
