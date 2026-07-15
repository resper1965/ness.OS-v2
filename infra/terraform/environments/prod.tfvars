# =============================================================================
# Valores de Produção - zabbix.ness
# =============================================================================
# ATENÇÃO: Este arquivo contém placeholders para credenciais sensíveis.
#          NÃO commite este arquivo com valores reais no Git!
#
# Alternativas seguras para fornecer credenciais:
#   1. Variáveis de ambiente:
#      export TF_VAR_contabo_oauth2_client_id="seu-client-id"
#      export TF_VAR_contabo_oauth2_client_secret="seu-client-secret"
#      export TF_VAR_contabo_oauth2_user="seu-email@exemplo.com"
#      export TF_VAR_contabo_oauth2_pass="sua-senha"
#      export TF_VAR_ssh_public_key="ssh-ed25519 AAAA... ness_admin@zabbix-ness"
#
#   2. Arquivo separado (não versionado):
#      Crie um arquivo secrets.auto.tfvars com as credenciais
#
#   3. HashiCorp Vault ou AWS Secrets Manager
# =============================================================================

# ---------------------------------------------------------------------------
# Credenciais OAuth2 da API Contabo
# Obtenha em: https://my.contabo.com/api/details
# ---------------------------------------------------------------------------
contabo_oauth2_client_id     = "SUBSTITUIR_PELO_CLIENT_ID"
contabo_oauth2_client_secret = "SUBSTITUIR_PELO_CLIENT_SECRET"
contabo_oauth2_user          = "SUBSTITUIR_PELO_EMAIL"
contabo_oauth2_pass          = "SUBSTITUIR_PELA_SENHA"

# ---------------------------------------------------------------------------
# Configurações da VPS - Cloud VPS V3
# 8 vCPU | 30 GB RAM | 800 GB SSD | ~€9.99/mês
# ---------------------------------------------------------------------------
# NOTA: Storage VPS (1.2 TB, €20/mês) não é suportado via API.
#       O Cloud VPS V3 é o equivalente mais próximo gerenciável via Terraform.
# ---------------------------------------------------------------------------
vps_display_name = "zabbix-ness-prod"
vps_product_id   = "V3"
vps_image_id     = "debian-12"
vps_region       = "EU"
vps_default_user = "ness_admin"
vps_period       = 1

# ---------------------------------------------------------------------------
# Configurações do Object Storage - 250 GB (€2.49/mês)
# ---------------------------------------------------------------------------
object_storage_region              = "EU"
object_storage_total_tb            = 0.25
object_storage_auto_scaling_enabled = false
object_storage_auto_scaling_limit_tb = 1

# ---------------------------------------------------------------------------
# Chave SSH
# ---------------------------------------------------------------------------
# Gere uma chave Ed25519 com:
#   ssh-keygen -t ed25519 -C "ness_admin@zabbix-ness" -f ~/.ssh/ness_admin
#
# Cole abaixo o conteúdo de ~/.ssh/ness_admin.pub
# ---------------------------------------------------------------------------
ssh_key_name   = "ness-admin-prod-key"
ssh_public_key = "SUBSTITUIR_PELA_CHAVE_PUBLICA_SSH"

# ---------------------------------------------------------------------------
# Metadados do Projeto
# ---------------------------------------------------------------------------
project_name = "zabbix-ness"
environment  = "prod"

# ---------------------------------------------------------------------------
# Configurações do Hub AIOps / Wazuh Hub (SOC)
# ---------------------------------------------------------------------------
hub_display_name = "aiops-soc-hub-prod"
hub_product_id   = "V3"

