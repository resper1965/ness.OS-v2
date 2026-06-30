# =============================================================================
# Outputs do Terraform - Informações Pós-Provisionamento
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Exporta informações essenciais dos recursos provisionados
#            para uso em automações, scripts e documentação.
# =============================================================================

# ---------------------------------------------------------------------------
# Outputs da Instância VPS
# ---------------------------------------------------------------------------

output "vps_instance_id" {
  description = "ID único da instância VPS na Contabo"
  value       = contabo_instance.zabbix_server.id
}

output "vps_display_name" {
  description = "Nome de exibição da instância VPS"
  value       = contabo_instance.zabbix_server.display_name
}

output "vps_ip_v4" {
  description = "Endereço IPv4 público da VPS (usar para acesso SSH e configuração DNS)"
  value       = contabo_instance.zabbix_server.ip_config[0].v4[0].ip
}

output "vps_ip_v6" {
  description = "Endereço IPv6 público da VPS"
  value       = contabo_instance.zabbix_server.ip_config[0].v6[0].ip
}

output "vps_product_id" {
  description = "Product ID utilizado (especificações de hardware)"
  value       = contabo_instance.zabbix_server.product_id
}

output "vps_image_id" {
  description = "Imagem do sistema operacional instalado"
  value       = contabo_instance.zabbix_server.image_id
}

output "vps_region" {
  description = "Região onde a VPS está provisionada"
  value       = contabo_instance.zabbix_server.region
}

output "vps_default_user" {
  description = "Usuário padrão para acesso SSH"
  value       = contabo_instance.zabbix_server.default_user
}

# ---------------------------------------------------------------------------
# Outputs do Object Storage
# ---------------------------------------------------------------------------

output "object_storage_id" {
  description = "ID único do Object Storage na Contabo"
  value       = contabo_object_storage.data_storage.id
}

output "object_storage_s3_url" {
  description = "URL S3 do Object Storage (endpoint para ferramentas S3-compatíveis)"
  value       = contabo_object_storage.data_storage.s3_url
}

output "object_storage_s3_tenant_id" {
  description = "Tenant ID para autenticação S3 (usado como parte das credenciais)"
  value       = contabo_object_storage.data_storage.s3_tenant_id
}

output "object_storage_region" {
  description = "Região do Object Storage"
  value       = contabo_object_storage.data_storage.region
}

output "object_storage_total_space_tb" {
  description = "Espaço total contratado em TB"
  value       = contabo_object_storage.data_storage.total_purchased_space_tb
}

# ---------------------------------------------------------------------------
# Outputs da Chave SSH
# ---------------------------------------------------------------------------

output "ssh_secret_id" {
  description = "ID do secret SSH na Contabo (referência para novas instâncias)"
  value       = contabo_secret.ssh_key.id
}

output "ssh_secret_name" {
  description = "Nome do secret SSH registrado"
  value       = contabo_secret.ssh_key.name
}

# ---------------------------------------------------------------------------
# Outputs Consolidados (úteis para scripts de automação)
# ---------------------------------------------------------------------------

output "connection_summary" {
  description = "Resumo das informações de conexão"
  value = {
    ssh_command    = "ssh ${contabo_instance.zabbix_server.default_user}@${contabo_instance.zabbix_server.ip_config[0].v4[0].ip}"
    s3_endpoint    = contabo_object_storage.data_storage.s3_url
    s3_tenant_id   = contabo_object_storage.data_storage.s3_tenant_id
    vps_ip         = contabo_instance.zabbix_server.ip_config[0].v4[0].ip
    instance_id    = contabo_instance.zabbix_server.id
    environment    = var.environment
  }
}
