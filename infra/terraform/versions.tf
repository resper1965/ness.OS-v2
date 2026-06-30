# =============================================================================
# Requisitos de Versão do Terraform e Providers
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Define as versões mínimas do Terraform e do provider Contabo
#            necessárias para garantir compatibilidade e estabilidade.
# =============================================================================

terraform {
  # Versão mínima do Terraform exigida
  required_version = ">= 1.5.0"

  required_providers {
    # Provider oficial da Contabo para gerenciamento de infraestrutura
    # Documentação: https://registry.terraform.io/providers/contabo/contabo/latest/docs
    contabo = {
      source  = "contabo/contabo"
      version = ">= 0.1.42"
    }
  }

  # =========================================================================
  # Backend de Estado (State)
  # =========================================================================
  # RECOMENDAÇÃO: Em produção, utilize um backend remoto para armazenar
  # o estado do Terraform de forma segura e compartilhada.
  #
  # Exemplo com S3 (compatível com Contabo Object Storage):
  #
  # backend "s3" {
  #   bucket                      = "zabbix-ness-terraform-state"
  #   key                         = "prod/terraform.tfstate"
  #   region                      = "us-east-1"
  #   endpoint                    = "https://eu2.contabostorage.com"
  #   skip_credentials_validation = true
  #   skip_metadata_api_check     = true
  #   skip_region_validation      = true
  #   force_path_style            = true
  # }
  # =========================================================================
}
