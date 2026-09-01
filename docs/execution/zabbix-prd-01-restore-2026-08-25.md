# Zabbix PRD-01 — restauração isolada aprovada (2026-08-25)

## Escopo

Restauração do backup aprovado `20260822T121154-0300` na VPS permanente
`ness-os-zabbix-prd-01` (`zbx-prd-01`), sem iniciar o Zabbix Server, sem DNS,
proxies, agentes, ações ou notificações de produção.

## Evidências

| Verificação | Resultado |
| --- | --- |
| SHA-256 do dump | `6c4a9ce636d0adb54747dea675f7c2d502f6f42b003365eeff4308237e552f6c` |
| Tempo de restore | 3.911 segundos |
| Tabelas | 203 |
| Hosts/templates | 674 |
| Itens | 60.250 |
| Triggers | 24.520 |
| Versão obrigatória do banco | `7000000` |
| Ações ativas | 5 → 0 |
| Mídias ativas | 1 → 0 |
| Conectores ativos | 0 → 0 |
| Zabbix Server | inativo e mascarado |
| Resultado | `restore=PASS` |

O banco restaurado ocupava aproximadamente 37 GB ao término. MariaDB permanece
localhost-only. Não há listener TCP em `10051` e o servidor Zabbix não foi
desmascarado nem iniciado.

## Próximo gate

Executar a auditoria offline/polimento e configurar a cópia Restic do novo
destino. Somente após UAT, controles de borda e aceite haverá plano de corte.
