# ness.OS — estágio em 2026-09-28

## Decisão de entrega

O MVP é o fluxo autenticado Zabbix → incidente no Hub → ticket GLPI, com isolamento de tenant, idempotência, auditoria e estado/frescor das fontes visíveis ao operador. Wazuh é pós-MVP e depende de aceite do MVP e aprovação de capacidade/custo. O plano mestre liga os oito critérios de aceite às tarefas e gates das Fases 0–4 e 6.

## Estado comprovado

| Frente | Estado | Base |
|---|---|---|
| Fase 0 / release | `FAIL` na última avaliação, de 26/09 | `docs/execution/gates/phase-0-recovery-release.md`; backup e restauração passaram, mas commit/digests, rollback e CI completo ainda bloqueiam release |
| Código local do Hub | Implementação em andamento | Fase 3 Task 1 concluída em `342a817`; falhas dos healthchecks dos workers deixam de ser mascaradas em `641a885` |
| Identidade e tenant | Matriz inicial, gate pendente | Inventário de rotas em `docs/security/access-control-matrix.md`; `operator`/`viewer` ainda não têm correspondência segura com papéis legados |
| MVP integrado | Não aceito | Fases 1–4 e 6 ainda têm tarefas e gates abertos; não há evidência dos oito critérios em uma release candidata |
| Wazuh | Planejado | Fora do gate do MVP; sem compra ou rollout autorizado por este plano |

Os testes locais executados nesta atualização foram `python3 -m pytest tests/test_authentik_rbac.py -q` (11 aprovados), Ruff check/format para esse teste, `bash infra/tests/test-aiops-runtime-readiness.sh` e `git diff --check`. O teste de readiness simula um worker parado; não substitui um exercício com contêiner real. Não houve nova coleta de saúde dos serviços ou de backups de produção nesta atualização. A evidência de 26/09 deve ser renovada antes de qualquer decisão de release.

## Próxima execução

1. Definir e testar o escopo de tenant do papel `operator` sem conceder acesso global de `noc`; manter a Fase 1 sem aprovação até o teste de isolamento passar em API e stream.
2. Completar a sonda da API para banco e Redis e provar a transição `unhealthy`/`healthy` de workers em ambiente de teste; o ajuste de `641a885` cobre o mascaramento de falha e a checagem de estado no readiness.
3. Avançar nos contratos locais Zabbix/GLPI e no fluxo idempotente; preservar a Fase 0 como gate para deploy e escritas em produção.
4. Reconciliar a release com os arquivos e imagens reais, CI e rollback antes de reavaliar a Fase 0.

A árvore da branch `feat/incidents-rbac-local` ainda contém alterações e arquivos não rastreados anteriores a esta atualização. Foram preservados; nenhum desses arquivos foi incluído nos três commits desta atualização (`4bf9c68`, `cf12f02`, `641a885`).
