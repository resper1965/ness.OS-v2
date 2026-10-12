# Zabbix — baseline de qualidade offline

Coleta: 12/10/2026 10:36:34 BRT, destino `169.58.234.9`, banco `dbzabbix`.
Servidor inativo e mascarado; MariaDB ativo; listener 10051 ausente.
Relatório root-only:
`/var/lib/ness-os/restore-evidence/offline-polish-baseline-20261012T103634-0300.txt`.
SHA-256: `088a5bb85d5fa5d2d89d3e6d4d97463e8170c1e91cd9565cb458ccd0692db51b`.

| Métrica do banco restaurado | Total |
| --- | ---: |
| Hosts configurados como monitorados | 314 |
| Templates | 362 |
| Itens habilitados nesses hosts | 43.304 |
| Itens não suportados | 2.887 |
| Triggers habilitadas com estado desconhecido | 1.320 |
| Hosts sem template | 20 |
| Hosts sem tags | 277 |
| Hosts com coordenadas | 248 |
| Ações, mídias, conectores habilitados | 0 |
| Escalations | 0 |

Categorias: timeout 2.124, other 492, authentication 159,
calculation_expression 59, preprocessing 34, connectivity_dns 13,
value_type 4 e key_metric_oid 2.

Prioridade: confirmar conectividade/timeout e credenciais na origem, depois
templates/cálculos/preprocessing. Planejar tags e template dos ativos piloto
em lotes de cinco, com export prévio e rollback. Não aplicar correções em massa
nem considerar timeout do banco restaurado como falha corrente.

O relatório foi gerado agora, mas os estados de telemetria são históricos do
restore. A origem produtiva não foi consultada intensivamente fora da janela
22:00–00:00 BRT. A classificação atual depende dessa revalidação na janela.
