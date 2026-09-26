# Gate da Fase 0 — recuperação e baseline de release

**Resultado geral: FAIL — não autoriza release nem início de fases dependentes.**

Avaliação atualizada em 2026-09-26 (America/Sao_Paulo), considerando somente as VPS do
projeto: AIOps `144.91.115.242`, Zabbix canônico `144.91.72.202` e o destino de
UAT/cutover pendente `169.58.234.9`. `npentest` (`169.58.178.187`) está fora do
escopo.

**Limite da atualização:** em 26/09 foram renovadas as evidências de backup e
restore externo do AIOps; consulte
[`phase-0-aiops-recovery-2026-09-26.md`](../evidence/phase-0-aiops-recovery-2026-09-26.md).
O manifesto ainda compara arquivos/imagens aos fatos de produção de 25/09 às
17:49 BRT. A UAT responde por SSH com a chave própria e continua com o servidor
Zabbix isolado; contudo, o token da integração canônica não está autorizado na
UAT. O Zabbix canônico expirou na porta 22. O OAuth da Contabo retornou HTTP 403
antes de emitir token; a consulta GET sem token retornou HTTP 401, então o
inventário do plano de controle não foi renovado. O estado recente do AIOps não
atualiza hashes de código/imagens. Consulte
[`zabbix-uat-readonly-baseline-2026-09-26.md`](../evidence/zabbix-uat-readonly-baseline-2026-09-26.md).
O registro desta retomada está em
[`ness-os-operationalization-log.md`](../ness-os-operationalization-log.md).

| Critério | Estado | Evidência |
|---|---|---|
| Backup local Hub e Zabbix com menos de 24 h | PASS | Hub/AIOps `20260925T230000-0300`, `COMPLETED` presente e as 24 entradas de checksum aprovadas; Zabbix `20260925T220022-0300`, manifesto/checksums aprovados na coleta anterior. Ambos tinham menos de 24 h às 16:07 BRT de 26/09. |
| Cópia externa correspondente aos conjuntos atuais | PASS | AIOps: Restic snapshot `d66d36f3` corresponde ao conjunto `20260925T230000-0300`; restore isolado de 860,216 MiB com `--verify`, 26 arquivos verificados e checksums aprovados. Zabbix snapshot `15a5ef41` corresponde a `20260925T220022-0300`; `restic check` completo e restore isolado aprovados na evidência de 25/09. A retenção AIOps/Zabbix não foi alterada nesta validação. |
| Restaurações isoladas Hub, Zabbix e Psono | PASS | AIOps: snapshot atual restaurado e checksums/manifesto aprovados em 26/09; Psono restaurado em 25/09 do conjunto `20260925T013239-0300` (51 tabelas, HTTP 200, assinatura válida e chave pública correspondente); Zabbix `15a5ef41` (203 tabelas, 685 hosts, 64.226 itens, 26.697 triggers, 362 templates e `dbversion.mandatory=7000000`). Ambientes temporários removidos. |
| Timers habilitados, última execução aprovada e próxima execução | PASS | Hoje no AIOps: timer local ativo, último disparo 25/09 23:00, próximo 26/09 23:00; timer externo ativo, última execução 26/09 00:30:50 e próxima 27/09 00:30 BRT. Zabbix externo estava ativo e com próxima execução 27/09 05:30 na coleta anterior. |
| Produção ligada a commit e imagens imutáveis; rollback ensaiado | FAIL | A árvore contém mudanças pendentes; 8 de 19 imagens não têm digest; 43 arquivos montados/instalados divergem dos fatos remotos conhecidos e 47 ainda não têm hash remoto observado. Não há ensaio de rollback associado à release. Consulte `../evidence/phase-0-production-manifest.json`. |
| `git diff --check` e verificações locais | PASS | A checagem da árvore terminou sem erros. Backend: Pytest 264 aprovados; Black 111 arquivos, Ruff check/format 77 arquivos, MyPy 77 arquivos e Flake8 E9/F63/F7/F82 sem erros. Frontend em cópia temporária limpa: Oxlint, TypeScript e build passaram; Oxlint reportou um aviso Fast Refresh. Infraestrutura: 15 testes shell, 18 testes Python (+ 3 subtests) passaram; migração SQL aplicada duas vezes em PostgreSQL 17 isolado e 16 scripts PHP passaram lint em PHP 8.1. Sete utilitários GLPI/Zabbix e o cutover Cavan abortaram em modo padrão sem `--apply`; o emissor sintético exige `--apply` e passou teste sem rede. Nesta retomada, o backend completo passou (264, 2 avisos `datetime.utcnow`), fixture Node dos workflows passou, o relatório de readiness comprovou presença/força do segredo sem exibi-lo e o manifesto passou 9 testes. O workflow completo em runner GitHub ainda não foi reexecutado. |

## Ações necessárias para reavaliar

1. Cópia externa, revisão de retenção, `restic check`, restore isolado e
   atualização do script Zabbix foram concluídos para o conjunto atual. Manter
   observação do timer; a seleção de parent incremental será comprovada na
   próxima execução agendada.
2. Revisar e agrupar as mudanças pendentes por domínio; comparar todos os hashes
   e imagens reais com a versão consolidada, publicar imagens próprias com digest
   imutável e ensaiar rollback.
3. Verificações locais atuais do backend e frontend passaram; executar os
   workflows completos em runner limpo após consolidar as mudanças por domínio,
   incluir SBOM e confirmar árvore limpa antes de reavaliar o gate.

Nenhum corte para `169.58.234.9`, tag de release ou trabalho dependente está
autorizado por este resultado. A onda Zabbix também continua bloqueada pela
permissão ausente para `template.get` e pela validação autenticada atual da UAT;
o vínculo do host `10977` no GLPI já foi confirmado em leitura somente.
