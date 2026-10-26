# Non-secret values only. Credentials come from TF_VAR_contabo_oauth2_* (see infra/docs/iac.md).
# Mirrors the Contabo API (read 26/10/2026). Keys match infra/ansible inventory groups.
instances = {
  zabbix_prod = { display_name = "ninfraops-zabbix", product_id = "V102", image_id = "4efbc0ba-2313-4fe1-842a-516f8652e729", region = "EU" } # vmi3409070, 144.91.72.202
  aiops       = { display_name = "aiops", product_id = "V98", image_id = "4efbc0ba-2313-4fe1-842a-516f8652e729", region = "EU" }              # vmi3409271, 144.91.115.242
  zabbix_uat  = { display_name = "ness-os-zabbix-prd-01", product_id = "V156", image_id = "d64d5c6c-9dda-4e38-8174-0ee282474d8a", region = "EU" } # vmi3532557, 169.58.234.9
}

object_storage_region                = "European Union" # API spelling; "EU" would show a diff
object_storage_total_tb              = 0.25
object_storage_auto_scaling_enabled  = false
object_storage_auto_scaling_limit_tb = 0

project_name = "zabbix-ness"
environment  = "prod"
