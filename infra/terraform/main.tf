# =============================================================================
# Recursos Principais - Infraestrutura Contabo
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Provisiona uma Cloud VPS + Object Storage na Contabo para
#            hospedar o servidor Zabbix com armazenamento S3-compatível.
#
# IMPORTANTE: O Contabo Storage VPS não é suportado pela API/Terraform.
#             Utilizamos Cloud VPS (V3 = 8 vCPU, 30 GB RAM, 800 GB SSD)
#             como alternativa equivalente gerenciável via IaC.
# =============================================================================

# ---------------------------------------------------------------------------
# Provider Contabo - Autenticação OAuth2
# ---------------------------------------------------------------------------
# As credenciais podem ser fornecidas via:
#   1. Arquivo .tfvars (NÃO commitar no Git!)
#   2. Variáveis de ambiente: TF_VAR_contabo_oauth2_client_id, etc.
#   3. HashiCorp Vault ou similar em produção
# ---------------------------------------------------------------------------
provider "contabo" {
  oauth2_client_id     = var.contabo_oauth2_client_id
  oauth2_client_secret = var.contabo_oauth2_client_secret
  oauth2_user          = var.contabo_oauth2_user
  oauth2_pass          = var.contabo_oauth2_pass
}

# ---------------------------------------------------------------------------
# Chave SSH - Secret para Acesso Remoto
# ---------------------------------------------------------------------------
# Armazena a chave pública SSH na conta Contabo para reutilização
# em múltiplas instâncias. O tipo "ssh" indica chave SSH pública.
# ---------------------------------------------------------------------------
resource "contabo_secret" "ssh_key" {
  name  = var.ssh_key_name
  type  = "ssh"
  value = var.ssh_public_key
}

# ---------------------------------------------------------------------------
# Instância Cloud VPS - Servidor Zabbix
# ---------------------------------------------------------------------------
# Provisiona a VPS principal para o servidor de monitoramento.
# O product_id define as especificações de hardware (vCPU, RAM, SSD).
#
# Mapeamento de Product IDs (verifique valores atualizados na API):
#   V1 = 4 vCPU, 8 GB RAM, 200 GB SSD
#   V2 = 6 vCPU, 16 GB RAM, 400 GB SSD
#   V3 = 8 vCPU, 30 GB RAM, 800 GB SSD  ← Recomendado para Zabbix
#   V4 = 12 vCPU, 60 GB RAM, 1.6 TB SSD
# ---------------------------------------------------------------------------
resource "contabo_instance" "zabbix_server" {
  display_name = var.vps_display_name
  product_id   = var.vps_product_id
  image_id     = var.vps_image_id
  region       = var.vps_region
  period       = var.vps_period
  default_user = var.vps_default_user

  # Referencia a chave SSH criada acima pelo ID do secret
  ssh_keys = [contabo_secret.ssh_key.id]

  # O lifecycle prevent_destroy protege contra destruição acidental
  # em produção. Remova este bloco se precisar recriar a instância.
  lifecycle {
    prevent_destroy = false # Altere para true em produção estável
  }
}

# ---------------------------------------------------------------------------
# Object Storage S3-Compatível - Armazenamento de Dados
# ---------------------------------------------------------------------------
# Provisiona o Object Storage na região EU para armazenamento de:
#   - Backups do banco de dados Zabbix
#   - Exportações de relatórios e gráficos
#   - Logs arquivados e dados históricos
#
# NOTA: Apenas UMA instância de Object Storage é permitida por região.
# Após provisionamento, gerencie buckets via AWS CLI ou provider AWS S3.
# ---------------------------------------------------------------------------
resource "contabo_object_storage" "data_storage" {
  region                   = var.object_storage_region
  total_purchased_space_tb = var.object_storage_total_tb

  # Auto-scaling: upgrade automático de espaço quando necessário
  # Habilite com cautela - cada upgrade gera cobrança adicional mensal
  auto_scaling {
    state         = var.object_storage_auto_scaling_enabled ? "enabled" : "disabled"
    size_limit_tb = var.object_storage_auto_scaling_limit_tb
  }
}

# ---------------------------------------------------------------------------
# Instância Cloud VPS - AIOps Hub (Orquestração NOC + SOC)
# ---------------------------------------------------------------------------
# Provisiona a VPS dedicada para PostgreSQL, Redis, n8n, Evolution API.
# V2 = 6 vCPU, 16 GB RAM, 400 GB NVMe (Ideal para o AIOps Hub)
# ---------------------------------------------------------------------------
resource "contabo_instance" "aiops_hub" {
  display_name = var.hub_display_name
  product_id   = var.hub_product_id
  image_id     = var.vps_image_id
  region       = var.vps_region
  period       = var.vps_period
  default_user = var.vps_default_user

  ssh_keys = [contabo_secret.ssh_key.id]

  lifecycle {
    prevent_destroy = false
  }
}

# ---------------------------------------------------------------------------
# Instância Cloud VPS - Wazuh Hub SOC (Centralizado)
# ---------------------------------------------------------------------------
resource "contabo_instance" "wazuh_hub" {
  display_name = var.wazuh_hub_display_name
  product_id   = var.wazuh_hub_product_id
  image_id     = var.vps_image_id
  region       = var.vps_region
  period       = var.vps_period
  default_user = var.vps_default_user

  ssh_keys = [contabo_secret.ssh_key.id]

  lifecycle {
    prevent_destroy = false
  }
}

# ---------------------------------------------------------------------------
# Instância Cloud VPS - Wazuh Spoke (Piloto do Cliente)
# ---------------------------------------------------------------------------
resource "contabo_instance" "wazuh_spoke" {
  display_name = var.wazuh_spoke_display_name
  product_id   = var.wazuh_spoke_product_id
  image_id     = var.vps_image_id
  region       = var.vps_region
  period       = var.vps_period
  default_user = var.vps_default_user

  ssh_keys = [contabo_secret.ssh_key.id]

  lifecycle {
    prevent_destroy = false
  }
}

