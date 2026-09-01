# Zabbix PRD-01 — gate Z-M1 aprovado (2026-08-28)

## Resultado

O snapshot Restic `96f2a24e`, conjunto `20260827T220026-0300`, foi restaurado
exclusivamente em staging no `zbx-prd-01`. Nenhum banco foi importado e o
Zabbix Server não foi iniciado.

| Controle | Evidência |
| --- | --- |
| Restore Restic | 10 arquivos/diretórios, 5,443 GiB em 6 min 09 s |
| Manifesto | 6 de 6 entradas SHA-256 válidas |
| Dump | `db/dbzabbix.sql.gz`, 5.843.841.423 bytes |
| Compressão | `gzip -t` aprovado |
| Serviço | `zabbix-server` mascarado e inativo |
| Listener | porta TCP `10051` ausente |
| Resultado | `staging_integrity=PASS`, gate Z-M1 aprovado |

## Incidente de validação

A primeira validação retornou falso negativo porque o `SHA256SUMS` preservava
caminhos absolutos da origem. O staging já continha todos os artefatos. O
prefixo `/var/backups/zabbix/nightly/20260827T220026-0300/` foi removido apenas
do fluxo de leitura do manifesto, sem alterar o manifesto ou os arquivos
restaurados; a repetição aprovou as seis entradas e o dump compactado.

## Próximo gate

Z-M2: criar um backup local reversível do banco atualmente instalado no
`zbx-prd-01` e só então importar o dump validado, mantendo origem, DNS, proxies,
agentes, ações, mídias e coleta produtiva inalterados.
