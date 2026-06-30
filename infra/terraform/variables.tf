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
# Configurações da Instância VPS (Cloud VPS)
# ---------------------------------------------------------------------------
# NOTA: O Contabo Storage VPS NÃO é suportado pela API/Terraform.
# Utilizamos Cloud VPS que é compatível com a API.
# Referência de product_id: consulte https://api.contabo.com/#tag/Products
# ---------------------------------------------------------------------------

variable "vps_display_name" {
  description = "Nome de exibição da instância VPS no painel Contabo"
  type        = string
  default     = "zabbix-ness-server"
}

variable "vps_product_id" {
  description = <<-EOT
    ID do produto VPS na Contabo. Exemplos:
    - "V1"  = Cloud VPS 1 (4 vCPU, 8 GB RAM, 200 GB SSD)
    - "V2"  = Cloud VPS 2 (6 vCPU, 16 GB RAM, 400 GB SSD)
    - "V3"  = Cloud VPS 3 (8 vCPU, 30 GB RAM, 800 GB SSD)
    - "V4"  = Cloud VPS 4 (12 vCPU, 60 GB RAM, 1.6 TB SSD)
    
    NOTA: Storage VPS não é suportado via API. Use Cloud VPS equivalente.
    Verifique IDs atualizados em: https://api.contabo.com/#tag/Products
  EOT
  type        = string
  default     = "V3"
}

variable "vps_image_id" {
  description = <<-EOT
    ID da imagem do sistema operacional para instalação na VPS.
    Use o data source 'contabo_image' ou a API para listar IDs disponíveis.
    
    Exemplos comuns:
    - "debian-12"     = Debian 12 (Bookworm)
    - "ubuntu-22.04"  = Ubuntu 22.04 LTS
    - "ubuntu-24.04"  = Ubuntu 24.04 LTS
    
    Verifique IDs atualizados em: https://api.contabo.com/#tag/Images
  EOT
  type        = string
  default     = "debian-12"
}

variable "vps_region" {
  description = <<-EOT
    Região para provisionamento da VPS.
    Regiões disponíveis: EU, US-central, US-east, US-west, SIN
  EOT
  type        = string
  default     = "EU"
}

variable "vps_default_user" {
  description = "Usuário padrão criado na instância VPS para acesso SSH"
  type        = string
  default     = "ness_admin"
}

variable "vps_period" {
  description = "Período de contratação em meses (1, 3, 6, 12)"
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 3, 6, 12], var.vps_period)
    error_message = "O período deve ser 1, 3, 6 ou 12 meses."
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
# Chave SSH para Acesso Remoto
# ---------------------------------------------------------------------------

variable "ssh_key_name" {
  description = "Nome descritivo da chave SSH no painel Contabo"
  type        = string
  default     = "ness-admin-ssh-key"
}

variable "ssh_public_key" {
  description = <<-EOT
    Chave pública SSH (conteúdo completo, formato OpenSSH).
    Exemplo: "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ... ness_admin@zabbix-ness"
    
    Gere uma nova chave com: ssh-keygen -t ed25519 -C "ness_admin@zabbix-ness"
  EOT
  type        = string
  sensitive   = true
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
