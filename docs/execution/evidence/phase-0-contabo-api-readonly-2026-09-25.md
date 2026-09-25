# Evidência de leitura da API Contabo — Fase 0

Coleta em 2026-09-25 às 18:38 BRT. A autenticação usou as credenciais já
disponíveis localmente; valores de credenciais e tokens não foram exibidos nem
registrados. Foram feitas somente requisições GET de inventário para os IPs
conhecidos do projeto. A VPS `npentest` foi excluída da consulta.

| IP | Instance ID | Instance name | Display name | Produto | Estado Contabo |
|---|---:|---|---|---|---|
| `144.91.115.242` | `203409271` | `vmi3409271` | `aiops` | Cloud VPS 30 SSD (no setup) | `running` |
| `144.91.72.202` | `203409070` | `vmi3409070` | `ninfraops-zabbix` | Storage VPS 40 (no setup) | `running` |
| `169.58.234.9` | `203532557` | `vmi3532557` | `ness-os-zabbix-prd-01` | Cloud VPS 12 (2026) (no setup) | `running` |

## Limite da evidência

O estado `running` vem do plano de controle da Contabo. Não comprova saúde do
sistema operacional, serviços, timer de backup, snapshot Restic, inventário
Zabbix ou disponibilidade de SSH. A checagem independente da UAT confirmou
`zabbix-server` inativo e mascarado; a API pública informa Zabbix `7.0.27` na
UAT e na URL canônica. O gate da Fase 0 permanece `FAIL` até comprovar os
requisitos de backup externo e release descritos em
`../gates/phase-0-recovery-release.md`.

O endpoint consultado foi `GET /v1/compute/instances` com busca por cada IP,
conforme a [documentação oficial da API Contabo](https://api.contabo.com/).
Nenhuma configuração, instância ou credencial foi alterada.
