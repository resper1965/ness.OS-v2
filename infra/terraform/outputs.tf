# =============================================================================
# Outputs do Terraform - Informações Pós-Provisionamento
# =============================================================================
# Projeto: zabbix.ness - Infraestrutura de Monitoramento
# Descrição: Exporta informações essenciais dos recursos provisionados
#            para uso em automações, scripts e documentação.
# =============================================================================

output "instances" {
  description = "Por chave: id, nome e IPv4 público das VPS"
  value = {
    for k, v in contabo_instance.vps : k => {
      id   = v.id
      name = v.display_name
      ipv4 = v.ip_config[0].v4[0].ip
    }
  }
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
