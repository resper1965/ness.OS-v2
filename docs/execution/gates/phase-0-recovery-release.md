# Gate da Fase 0 — recuperação e baseline de release

**Resultado geral: FAIL — não autoriza release nem início de fases dependentes.**

Avaliação em 2026-09-25 (America/Sao_Paulo), considerando somente as VPS do
projeto: AIOps `144.91.115.242`, Zabbix canônico `144.91.72.202` e o destino de
UAT/cutover pendente `169.58.234.9`. `npentest` (`169.58.178.187`) está fora do
escopo.

| Critério | Estado | Evidência |
|---|---|---|
| Backup local Hub e Zabbix com menos de 24 h | PASS | Hub `20260925T122220-0300`; Zabbix `20260925T162305-0300`, ambos com manifesto e checksums aprovados. |
| Cópia externa correspondente aos conjuntos atuais | FAIL | Hub tem snapshot Restic verificado ligado a `20260925T122220-0300`; snapshot do Zabbix não foi comprovado. Timer externo do Zabbix está desabilitado. |
| Restaurações isoladas Hub, Zabbix e Psono | FAIL | Hub e Zabbix passaram. A última validação isolada Psono ocorreu em 20/09 e não está associada ao backup Psono atual de 25/09. |
| Timers habilitados, última execução aprovada e próxima execução | FAIL | Timers Hub/Psono estão ativos. O backup local Zabbix catch-up terminou com sucesso e o próximo está marcado para 22:00; o timer externo Zabbix continua desabilitado. |
| Produção ligada a commit e imagens imutáveis; rollback ensaiado | FAIL | A árvore contém mudanças pendentes; API/frontend/workers não têm digest publicado; Compose Hub e Caddy Psono divergem. Não há ensaio de rollback associado à release. Consulte `../evidence/phase-0-production-manifest.json`. |
| `git diff --check` e testes desta fase | FAIL | Os cinco testes do manifesto passaram e os arquivos staged da Task 4 passaram no diff check. A árvore completa ainda acusa whitespace em `infra/tests/test-object-storage-restic-tooling.sh:76`; as demais mudanças preexistentes não foram consolidadas nem testadas como grupos. |

## Ações necessárias para reavaliar

1. Depois de resolver a rotação pendente de credenciais, habilitar e provar o
   snapshot externo Zabbix correspondente ao conjunto local atual.
2. Fazer e documentar restauração isolada do conjunto Psono atual.
3. Revisar e agrupar as mudanças pendentes por domínio; comparar todos os hashes
   e imagens reais com a versão consolidada, publicar imagens próprias com digest
   imutável e ensaiar rollback.
4. Corrigir o whitespace apontado, executar os testes e CI aplicáveis, confirmar
   árvore limpa e só então reavaliar o gate.

Nenhum corte para `169.58.234.9`, tag de release ou trabalho dependente está
autorizado por este resultado.
