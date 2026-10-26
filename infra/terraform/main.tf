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

# Existing VPS, imported (imports.tf). Attributes the provider cannot change in place
# (image/ssh keys/default user) are ignored so a drift never forces a replace.
resource "contabo_instance" "vps" {
  for_each = var.instances

  display_name = each.value.display_name
  product_id   = each.value.product_id
  image_id     = each.value.image_id
  region       = each.value.region

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image_id, ssh_keys, default_user, region] # region: provider does not read it back on import
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
