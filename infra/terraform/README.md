# Terraform — Contabo

Imports and protects the existing VPS (`zabbix_prod`, `aiops`, `zabbix_uat`) and the Object Storage; the only new host is the optional Wazuh R3a VPS (`var.wazuh_r3a`, null by default; see `docs/runbooks/wazuh-r3a-provisionamento.md`).

How to run (wrapper, variables, plan → guard → apply, import, safe destruction): [`infra/docs/iac.md`](../docs/iac.md).
