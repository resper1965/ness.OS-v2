# =============================================================================
# Requisitos de Versão do Terraform e Providers
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Define as versões mínimas do Terraform e do provider Contabo
#            necessárias para garantir compatibilidade e estabilidade.
# =============================================================================

terraform {
  # Versão mínima do Terraform exigida
  required_version = ">= 1.7.0"

  required_providers {
    # Provider oficial da Contabo para gerenciamento de infraestrutura
    # Documentação: https://registry.terraform.io/providers/contabo/contabo/latest/docs
    contabo = {
      source  = "contabo/contabo"
      version = ">= 0.1.42"
    }
  }

  # Estado remoto: bucket próprio, privado e versionado (Task 1.1). Credenciais
  # AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY vêm do ambiente (infra/bin/tf).
  # ponytail: sem lock (S3 compatível da Contabo, sem DynamoDB); upgrade path:
  # use_lockfile = true quando o Terraform >= 1.10 for fixado e o endpoint suportar.
  backend "s3" {
    bucket                      = "ness-os-tfstate"
    key                         = "prod/terraform.tfstate"
    region                      = "default"
    endpoints                   = { s3 = "https://eu2.contabostorage.com" }
    use_path_style              = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true
  }
}
