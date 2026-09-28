# ness.OS — estágio em 2026-09-28

## Decisão de entrega

O MVP é o fluxo autenticado Zabbix → incidente no Hub → ticket GLPI, com isolamento de tenant, idempotência, auditoria e estado/frescor das fontes visíveis ao operador. Wazuh é pós-MVP e depende de aceite do MVP e aprovação de capacidade/custo. O plano mestre liga os oito critérios de aceite às tarefas e gates das Fases 0–4 e 6.

## Estado comprovado

| Frente | Estado | Base |
|---|---|---|
| Fase 0 / release | `FAIL` na última avaliação, de 26/09 | `docs/execution/gates/phase-0-recovery-release.md`; backup e restauração passaram, mas commit/digests, rollback e CI completo ainda bloqueiam release |
| Código local do Hub | Implementação em andamento | Fase 3 Task 1 concluída em `342a817`; workers falham fechado em `641a885`; a sonda `/ready` verifica PostgreSQL, esquema de incidente, Redis da aplicação e broker Celery. O ensaio local com containers mostrou `200` → `503` → `200` na queda e retorno do Redis e confirmou as sondas dos dois workers; falta exercício do Compose completo no ambiente alvo |
| Identidade e tenant | Papéis locais implementados; gate pendente | Inventário de rotas em `docs/security/access-control-matrix.md`; HTTP e SSE revalidam papel, tenant e versão de sessão, e logout incrementa `session_epoch`. Grupos Authentik `operator` e `viewer` mapeiam para papéis com tenant obrigatório; `operator` pode agir somente em incidentes do próprio tenant e `viewer` apenas lê. Testes cobrem API, stream e migração local; falta UAT integrada da Fase 1 |
| MVP integrado | Não aceito | O detalhe restringe usuários de tenant; ações exigem papel NOC/SOC/admin ou `operator` no próprio tenant, usam bloqueio de linha e persistem histórico. Ingestão e resolução registram incidente, ticket, falha GLPI e ACK Zabbix. `/webhook/zabbix` e `/v1/alerts` enfileiram o mesmo worker por evento. O fluxo passou em PostgreSQL/Redis locais com APIs externas simuladas, inclusive resposta GLPI perdida, reentrega, replay, isolamento de tenant e recuperação Zabbix; ver `docs/execution/evidence/local-hub-flow-2026-09-28.md`. HTTP, chave de máquina, fila Celery e worker também passaram juntos em containers descartáveis; ver `docs/execution/evidence/local-hub-http-celery-flow-2026-09-28.md`. O painel já distingue último sucesso, falha e dado desatualizado para Zabbix, Atera e GLPI; Wazuh aparece como planejado. Ainda faltam UAT com sistemas reais e gates das Fases 1–4 e 6 |
| Wazuh | Planejado | Fora do gate do MVP; sem compra ou rollout autorizado por este plano |

Os testes locais executados até aqui foram a suíte completa do backend (379 aprovados na primeira rodada, um teste integrado opcional ignorado sem containers e dois avisos de depreciação), typecheck, lint e build do frontend, Ruff nos 79 módulos Python da aplicação, Black nos 119 arquivos do backend, MyPy nos 79 módulos e `bash infra/tests/test-aiops-runtime-readiness.sh`. O teste integrado opcional passou separadamente com PostgreSQL e Redis descartáveis. O workflow `ci-backend.yml` inclui esse teste em containers descartáveis e passou no runner GitHub do PR rascunho #64. O bootstrap SQL e a migração passaram na imagem PostgreSQL 16/TimescaleDB fixada pelo Compose, inclusive com esquema anterior aos novos papéis; ver `docs/execution/evidence/local-hub-schema-bootstrap-2026-09-28.md` e `docs/execution/evidence/local-hub-rbac-migration-2026-09-28.md`. O ensaio de readiness com containers está em `docs/execution/evidence/local-hub-container-readiness-2026-09-28.md`. Isso não substitui o exercício do stack real. Não houve nova coleta de saúde dos serviços ou de backups de produção nesta atualização. A evidência de 26/09 deve ser renovada antes de qualquer decisão de release.

O gerador do manifesto de release foi corrigido para registrar uma única vez cada bloqueio de imagem sem digest quando recebe fatos de produção. A regressão passou nos 10 testes do gerador. O bloqueio e o estado `FAIL` da Fase 0 continuam válidos; o manifesto histórico em `docs/execution/evidence/phase-0-production-manifest.json` não foi reescrito.

O workflow `ci-backend.yml` também passou a executar os 10 testes do manifesto, os testes de proteção das sondas de readiness e a validação do Compose mesclado com arquivos de ambiente fictícios e nenhum container iniciado. Os cinco workflows do [PR rascunho #64](https://github.com/resper1965/n-infraops/pull/64) (backend, frontend, lint e tipos, secret scan e SBOM) passaram no commit `4dc9477`. A exceção de Gitleaks cobre apenas linhas de hashes SHA-256 de arquivos no manifesto histórico; o diff Git e o snapshot rastreado foram verificados. A validação estrutural do Compose não substitui a execução do stack. Este resultado não altera o `FAIL` da Fase 0 nem autoriza release.

A lista de incidentes agora informa o total filtrado, permite carregar páginas seguintes e usa ordem estável por data e ID. A interface busca novamente os dados persistidos ao receber um evento SSE, evitando mostrar um evento parcial como cartão completo. A suíte do backend passou com 380 testes aprovados e um teste integrado opcional ignorado; o frontend passou em typecheck, lint e build. Para a suíte completa local, `pywebpush` e suas dependências foram instalados apenas em `/tmp`, pois não estavam no Python do ambiente. Esta validação não substitui a UAT integrada.

As rotas de leitura da Contabo agora retornam um erro genérico ao cliente e registram somente o tipo da falha do provedor, evitando exposição acidental de detalhes de SDK, HTTP ou credenciais. A suíte completa do backend passou novamente com 383 testes aprovados e um teste opcional ignorado.

Os contratos de alerta, incidente e pós-incidente agora geram timestamps UTC com fuso explícito; o despacho SecOps conserva o sufixo `Z`. A suíte completa voltou a passar com 383 testes e um ignorado, sem os avisos de `datetime.utcnow` observados antes.

As leituras e contagens Atera agora também ocultam detalhes do provedor quando a fonte falha, preservando somente um estado degradado identificável. A suíte completa passou com 385 testes aprovados e um ignorado.

As rotas do dashboard passaram a devolver somente estados e mensagens genéricas quando Zabbix ou Atera falham; logs registram apenas o tipo da exceção. A cobertura protege resumo, painel unificado e lista de problemas contra o vazamento de detalhes do provedor. A suíte completa passou com 388 testes aprovados e um ignorado.

As quatro rotas expostas de Atera RMM usam agora uma resposta genérica para falhas do provedor e um único registro seguro do tipo de erro. A suíte completa passou com 392 testes aprovados e um ignorado.

As consultas de tenants passaram a ocultar detalhes de exceções do banco, mantendo uma resposta operacional genérica. A suíte completa passou com 394 testes aprovados e um ignorado.

O módulo Contabo de gerenciamento, mantido fora do roteamento público, também passou a registrar apenas o tipo de falha e a devolver uma mensagem genérica se for ativado futuramente. A suíte completa passou com 395 testes aprovados e um ignorado.

Os indicadores do Core deixaram de transformar falha de coleta em zero: fontes indisponíveis retornam `null` e estado `unavailable`, preservando a semântica do contrato executivo. A suíte completa passou com 396 testes aprovados e um ignorado.

As estatísticas de triagem SecOps agora são derivadas das decisões persistidas em `SocDecision`, em vez de contadores por processo. Reinícios e múltiplos workers preservam os totais de bypass e encaminhamento de LLM. Sem decisões, a taxa fica `null` e o estado é `unavailable`, sem simular 100%. A suíte completa passou com 397 testes aprovados e um ignorado.

O cliente Atera passou a ocultar a exceção original no resumo; o Core utiliza esse resumo efetivamente implementado e conserva a indisponibilidade da fonte. A suíte completa passou com 399 testes aprovados e um ignorado.

O precheck somente leitura de 28/09 passou em 60 testes de sessão/RBAC, nos gates estáticos e nas rotas públicas Authentik, Hub, GLPI, n8n e Zabbix UAT. O Zabbix UAT permanece `inactive`, `masked` e sem escuta TCP/10051; ver `docs/execution/evidence/uat-readonly-precheck-2026-09-28.md`. Não houve login nominal nem confirmação do isolamento na aplicação implantada. O SSH de leitura à VPS AIOps foi negado pela chave disponível nesta sessão, portanto não há atualização de backups ou runtime de produção.

## Próxima execução

1. Executar UAT integrada dos papéis `operator` e `viewer` com Authentik e tenants reais, confirmando o isolamento na API e no stream antes de aprovar a Fase 1.
2. Exercitar o Compose completo no ambiente alvo, inclusive a transição de estado de saúde observada pelo Docker; o ensaio local já comprovou as respostas da API e das sondas Celery com processos reais.
3. Homologar o fluxo HTTP/Celery com Zabbix e GLPI reais em ambiente autorizado, inclusive falha parcial e replay; o ensaio local com as APIs simuladas já passou. Preservar a Fase 0 como gate para deploy e escritas em produção.
4. Reconciliar a release com os arquivos e imagens reais, CI e rollback antes de reavaliar a Fase 0.

A árvore da branch `feat/incidents-rbac-local` ainda contém alterações e arquivos não rastreados anteriores a esta atualização. Eles permanecem fora dos commits de implementação desta etapa.
