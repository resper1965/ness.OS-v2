# Gate da Fase 0 — recuperação e baseline de release

**Resultado geral: FAIL — não autoriza release nem início de fases dependentes.**

Avaliação atualizada em 2026-09-27 (America/Sao_Paulo), considerando somente as VPS do
projeto: AIOps `144.91.115.242`, Zabbix canônico `144.91.72.202` e o destino de
UAT/cutover pendente `169.58.234.9`. `npentest` (`169.58.178.187`) está fora do
escopo.

**Limite da atualização:** em 27/09 foram renovadas as evidências do backup
AIOps de 26/09, do snapshot externo correspondente e do restore isolado; consulte
[`phase-0-aiops-recovery-2026-09-27.md`](../evidence/phase-0-aiops-recovery-2026-09-27.md)
e o registro anterior de 26/09 em
[`phase-0-aiops-recovery-2026-09-26.md`](../evidence/phase-0-aiops-recovery-2026-09-26.md).
O manifesto ainda compara arquivos/imagens aos fatos de produção de 25/09 às
17:49 BRT. Em 27/09, a UAT respondeu por SSH com a chave própria e retornou
Zabbix 7.0.27; o token da integração continua sem autorização para `template.get`
na UAT em chamada via túnel. O Zabbix canônico expirou na porta 22 na
sonda de 27/09. Em 26/09, o OAuth da Contabo retornou
HTTP 403; a leitura autenticada foi renovada em 27/09 e confirmou as três VPS do
projeto em execução, com a pentest excluída. A leitura do firewall do provedor
mostrou a política `ness` inativa. SSH em `144.91.72.202:22` expira; a porta
`2222` documentada responde, mas rejeita a chave local com
`Permission denied (publickey)`. A última validação do host canônico e do token
canônico nele continua sendo a de 26/09; não estava autorizado para `template.get`.
Inventário
Contabo não atualiza hashes de código/imagens. Consulte
[`zabbix-uat-readonly-baseline-2026-09-26.md`](../evidence/zabbix-uat-readonly-baseline-2026-09-26.md).
Para a verificação UAT de 27/09, consulte
[`phase-1-identity-uat.md`](../evidence/phase-1-identity-uat.md).
Para a leitura Contabo e a sonda SSH de 27/09, consulte
[`phase-0-contabo-readonly-2026-09-27.md`](../evidence/phase-0-contabo-readonly-2026-09-27.md).
O registro desta retomada está em
[`ness-os-operationalization-log.md`](../ness-os-operationalization-log.md).

Esta atualização não renovou backup/API do Zabbix nem hashes/digests de produção.
O Zabbix canônico continua inacessível por SSH; por isso os critérios de backup
recente, cópia externa atual e timers do Zabbix permanecem `FAIL` até evidência
atual. O gate de release continua **FAIL**.

| Critério | Estado | Evidência |
|---|---|---|
| Backup local Hub e Zabbix com menos de 24 h | FAIL — parcial | AIOps atualizado em 27/09: conjunto `20260926T230011-0300`, `COMPLETED`, checksums aprovados; tinha 13h27 na coleta. Para Zabbix, o último conjunto comprovado segue `20260925T220022-0300`, com mais de 24 h; não foi possível renovar porque a chave SSH em `144.91.72.202:2222` foi rejeitada. |
| Cópia externa correspondente aos conjuntos atuais | FAIL — parcial | AIOps: Restic snapshot `4ca60242` corresponde a `20260926T230011-0300`; restore isolado de 862,761 MiB com `--verify`, 26 arquivos verificados e checksums aprovados em 27/09. Para Zabbix, o último conjunto comprovado é `20260925T220022-0300`; a cópia externa mais recente não foi verificada nesta retomada. |
| Restaurações isoladas Hub, Zabbix e Psono | PASS | AIOps: conjunto atual restaurado em 27/09; checksums/manifesto aprovados. Psono: restore de 25/09, conjunto `20260925T013239-0300` (51 tabelas, HTTP 200, assinatura válida e chave pública correspondente). Zabbix: snapshot `15a5ef41` (203 tabelas, 685 hosts, 64.226 itens, 26.697 triggers, 362 templates e `dbversion.mandatory=7000000`). Ambientes temporários removidos. |
| Timers habilitados, última execução aprovada e próxima execução | FAIL — parcial | AIOps: ambos os timers ativos, serviços concluíram com `Result=success` e código 0; próxima execução local 27/09 23:00 e externa 28/09 00:30 BRT. Timers/resultados atuais do Zabbix não foram verificados porque a chave SSH para a porta documentada 2222 foi rejeitada; a evidência anterior não comprova o disparo seguinte. |
| Produção ligada a commit e imagens imutáveis; rollback ensaiado | FAIL | O candidato local limpo `ec76784` ainda não tem release; 8 de 19 imagens não têm digest. A comparação remota de 25/09 registrou 43 divergências e 47 arquivos sem hash observado; não há rollback ensaiado associado ao candidato atual. Consulte `../evidence/phase-0-production-manifest.json` e `../evidence/phase-0-local-release-manifest-2026-09-27.json`. |
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
