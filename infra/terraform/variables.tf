# =============================================================================
# Variáveis do Terraform - Infraestrutura Contabo
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Todas as variáveis necessárias para provisionar a VPS e o
#            Object Storage na Contabo.
# =============================================================================

# ---------------------------------------------------------------------------
# Credenciais OAuth2 da API Contabo
# ---------------------------------------------------------------------------
# ATENÇÃO: Nunca commite credenciais em repositórios Git!
# Use variáveis de ambiente (TF_VAR_*) ou arquivos .tfvars locais.
# Obtenha as credenciais em: https://my.contabo.com/api/details
# ---------------------------------------------------------------------------

variable "contabo_oauth2_client_id" {
  description = "Client ID OAuth2 da API Contabo (obtido no painel de controle)"
  type        = string
  sensitive   = true
}

variable "contabo_oauth2_client_secret" {
  description = "Client Secret OAuth2 da API Contabo (obtido no painel de controle)"
  type        = string
  sensitive   = true
}

variable "contabo_oauth2_user" {
  description = "Usuário (e-mail) para autenticação OAuth2 na API Contabo"
  type        = string
  sensitive   = true
}

variable "contabo_oauth2_pass" {
  description = "Senha para autenticação OAuth2 na API Contabo"
  type        = string
  sensitive   = true
}

# ---------------------------------------------------------------------------
# VPS (Cloud VPS / Storage VPS) - uma entrada por instância, chave estável
# ---------------------------------------------------------------------------
variable "instances" {
  description = "VPS por chave estável (zabbix_prod, aiops, zabbix_uat, ...). Valores devem espelhar a API Contabo."
  type = map(object({
    display_name = string
    product_id   = string
    image_id     = string
    region       = string
  }))
}

# ---------------------------------------------------------------------------
# Wazuh R3a - sem default de propósito: product_id, image_id e ssh_key_ids não são adivinhados
# ---------------------------------------------------------------------------
variable "wazuh_r3a" {
  description = <<-EOT
    VPS do Wazuh R3a (opção B: Cloud VPS 12, 12 vCPU / 48 GB / 400 GB, 24 meses). null = não cria nada.
    product_id: confirmar no catálogo da API antes (somente leitura; ver o runbook).
    image_id: Ubuntu 24.04 (o instalador oficial do Wazuh suporta 24.04; Debian só com aviso).
    ssh_key_ids: secretIds (números) das chaves públicas já cadastradas na Contabo.
  EOT
  type = object({
    product_id  = string
    image_id    = string
    ssh_key_ids = list(number)
    region      = optional(string, "EU")
    period      = optional(number, 24)
  })
  default = null

  validation {
    condition     = var.wazuh_r3a == null ? true : length(var.wazuh_r3a.ssh_key_ids) > 0 && contains([1, 12, 24], var.wazuh_r3a.period)
    error_message = "wazuh_r3a: informe ao menos uma ssh_key_ids e period em 1, 12 ou 24."
  }
}

# ---------------------------------------------------------------------------
# Configurações do Object Storage (S3-compatível)
# ---------------------------------------------------------------------------

variable "object_storage_region" {
  description = <<-EOT
    Região do Object Storage S3-compatível da Contabo.
    Regiões disponíveis: EU, US-central, SIN
    
    NOTA: Apenas uma instância de Object Storage é permitida por região.
  EOT
  type        = string
  default     = "EU"
}

variable "object_storage_total_tb" {
  description = <<-EOT
    Espaço total do Object Storage em Terabytes.
    250 GB = 0.25 TB (plano de €2.49/mês)
    
    Valores comuns: 0.25, 0.5, 1, 2, 5
  EOT
  type        = number
  default     = 0.25
}

variable "object_storage_auto_scaling_enabled" {
  description = "Habilitar auto-scaling do Object Storage (upgrade automático mensal)"
  type        = bool
  default     = false
}

variable "object_storage_auto_scaling_limit_tb" {
  description = "Limite máximo de auto-scaling do Object Storage em Terabytes"
  type        = number
  default     = 1
}

# ---------------------------------------------------------------------------
# Tags e Metadados
# ---------------------------------------------------------------------------

variable "project_name" {
  description = "Nome do projeto para identificação dos recursos"
  type        = string
  default     = "zabbix-ness"
}

variable "environment" {
  description = "Ambiente de deploy (prod, staging, dev)"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["prod", "staging", "dev"], var.environment)
    error_message = "O ambiente deve ser: prod, staging ou dev."
  }
}
