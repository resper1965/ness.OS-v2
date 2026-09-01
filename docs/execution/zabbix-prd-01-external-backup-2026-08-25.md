# Zabbix PRD-01 — cópia externa criptografada aprovada (2026-08-25)

## Resultado

| Controle | Evidência |
| --- | --- |
| Backup local offline | `20260825T202327-0300`, `COMPLETED`, todos os SHA-256 válidos |
| Snapshot Restic | `60a22d18` |
| Conteúdo | 4,759 GiB (4,688 GiB armazenados) |
| Verificação | `restic check` e leitura de 5% dos packs sem erros |
| Restore externo isolado | 5.109.745.472 bytes restaurados |
| Checksums após restore | todos válidos |
| Resultado | `external_restore=PASS` |

O repositório usa prefixo exclusivo da nova VPS. O diretório temporário de
restauração foi removido após a validação; o snapshot foi preservado.

## Agenda

Os units de backup local e cópia externa estão instalados, mas os timers ficam
desabilitados enquanto `zabbix-server` permanece mascarado na UAT. Habilitá-los
é parte do gate de início controlado da coleta, evitando alertas de backup
falhos antes de existir uma rotina local elegível.
