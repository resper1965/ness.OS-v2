# Gate da Fase 0 — recuperação e baseline de release

**Resultado geral: FAIL — não autoriza release nem início de fases dependentes.**

Avaliação em 2026-09-25 (America/Sao_Paulo), considerando somente as VPS do
projeto: AIOps `144.91.115.242`, Zabbix canônico `144.91.72.202` e o destino de
UAT/cutover pendente `169.58.234.9`. `npentest` (`169.58.178.187`) está fora do
escopo.

| Critério | Estado | Evidência |
|---|---|---|
| Backup local Hub e Zabbix com menos de 24 h | PASS | Hub `20260925T122220-0300`; Zabbix `20260925T162305-0300`, ambos com manifesto e checksums aprovados. |
| Cópia externa correspondente aos conjuntos atuais | FAIL | Hub tem snapshot Restic verificado ligado a `20260925T122220-0300`; no Zabbix, último histórico do journal é 30/08 (`30c8f2d8`, ligado a `20260829T220005-0300`), cinco snapshots e `restic check` sem erros. Repositório `zabbix-prod` existe, mas não corresponde ao conjunto local atual; timer desabilitado. Env S3 root:root/0600; o script Zabbix (`1fe4ddf2…`) e AIOps (`2e968b34…`) diverge de `HEAD` (`afa3f1df…`). Veja [`phase-0-restic-script-drift-2026-09-25.md`](../evidence/phase-0-restic-script-drift-2026-09-25.md). |
| Restaurações isoladas Hub, Zabbix e Psono | PASS | Hub e Zabbix passaram. Psono restaurado em 25/09 do snapshot `20260925T013239-0300`: checksums OK, 51 tabelas, HTTP 200, assinatura válida e chave pública correspondente; containers/volume temporários removidos. |
| Timers habilitados, última execução aprovada e próxima execução | FAIL | Timers Hub/Psono estão ativos. O backup local Zabbix catch-up terminou com sucesso e o próximo está marcado para 22:00; o timer externo Zabbix continua desabilitado. |
| Produção ligada a commit e imagens imutáveis; rollback ensaiado | FAIL | A árvore contém mudanças pendentes; API/frontend/workers não têm digest publicado; 41 arquivos backend, Compose Hub e Caddy Psono divergem dos arquivos locais. Há 71 arquivos sem hash de produção e não há ensaio de rollback associado à release. Consulte `../evidence/phase-0-production-manifest.json`. |
| `git diff --check` e testes desta fase | PASS | `git diff --check` na árvore completa terminou com código zero. Os seis testes do manifesto, testes de backup/Restic/Zabbix/AIOps/Auth/Hub/Psono e verificações `bash -n` passaram. Os testes de grupos backend ainda pendentes não alteram este resultado de escopo da Fase 0; eles continuam bloqueando CI/reconciliação ampla. |

## Ações necessárias para reavaliar

1. Na janela, listar o repositório existente (não executar `init`), revisar `forget --dry-run` com a política configurada, instalar o script revisado e deixar `Persistent=true` disparar um único catch-up. Verificar snapshot, `restic check`, restauração isolada e checksums do conjunto local atual.
2. Revisar e agrupar as mudanças pendentes por domínio; comparar todos os hashes
   e imagens reais com a versão consolidada, publicar imagens próprias com digest
   imutável e ensaiar rollback.
3. Executar o CI dos grupos pendentes, consolidar os arquivos por domínio e
   confirmar árvore limpa antes de reavaliar o gate.

Nenhum corte para `169.58.234.9`, tag de release ou trabalho dependente está
autorizado por este resultado.
