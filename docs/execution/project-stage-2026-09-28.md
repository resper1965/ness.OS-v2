# ness.OS — estágio em 2026-09-28

## Decisão de entrega

O MVP é o fluxo autenticado Zabbix → incidente no Hub → ticket GLPI, com isolamento de tenant, idempotência, auditoria e estado/frescor das fontes visíveis ao operador. Wazuh é pós-MVP e depende de aceite do MVP e aprovação de capacidade/custo. O plano mestre liga os oito critérios de aceite às tarefas e gates das Fases 0–4 e 6.

## Estado comprovado

| Frente | Estado | Base |
|---|---|---|
| Fase 0 / release | `FAIL` na última avaliação, de 26/09 | `docs/execution/gates/phase-0-recovery-release.md`; backup e restauração passaram, mas commit/digests, rollback e CI completo ainda bloqueiam release |
| Código local do Hub | Implementação em andamento | Fase 3 Task 1 concluída em `342a817`; workers falham fechado em `641a885`; a sonda `/ready` da API verifica PostgreSQL, Redis da aplicação e broker Celery, mas falta exercício com containers reais |
| Identidade e tenant | Matriz inicial, gate pendente | Inventário de rotas em `docs/security/access-control-matrix.md`; HTTP e SSE revalidam papel, tenant e versão de sessão, e logout incrementa `session_epoch`; `operator`/`viewer` ainda não têm correspondência segura com papéis legados |
| MVP integrado | Não aceito | Fases 1–4 e 6 ainda têm tarefas e gates abertos; não há evidência dos oito critérios em uma release candidata |
| Wazuh | Planejado | Fora do gate do MVP; sem compra ou rollout autorizado por este plano |

Os testes locais executados até aqui foram a suíte completa do backend (286 aprovados antes do caso adicional de resposta Redis negativa), typecheck, lint e build do frontend, Ruff nos arquivos Python alterados e `bash infra/tests/test-aiops-runtime-readiness.sh`. O teste de readiness simula um worker parado; não substitui um exercício com contêiner real. A migração `session_epoch` ainda não foi aplicada ou testada em PostgreSQL isolado: o daemon Docker local está indisponível. Não houve nova coleta de saúde dos serviços ou de backups de produção nesta atualização. A evidência de 26/09 deve ser renovada antes de qualquer decisão de release.

## Próxima execução

1. Definir e testar o escopo de tenant do papel `operator` sem conceder acesso global de `noc`; manter a Fase 1 sem aprovação até o teste de isolamento passar em API e stream.
2. Provar a transição `unhealthy`/`healthy` da API e dos workers em ambiente com containers; os testes locais cobrem falhas de banco, Redis e broker, mas não o ciclo real do Docker.
3. Avançar nos contratos locais Zabbix/GLPI e no fluxo idempotente; preservar a Fase 0 como gate para deploy e escritas em produção.
4. Reconciliar a release com os arquivos e imagens reais, CI e rollback antes de reavaliar a Fase 0.

A árvore da branch `feat/incidents-rbac-local` ainda contém alterações e arquivos não rastreados anteriores a esta atualização. Eles permanecem fora dos commits de implementação desta etapa.
