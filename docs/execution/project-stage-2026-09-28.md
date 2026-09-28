# ness.OS — estágio em 2026-09-28

## Decisão de entrega

O MVP é o fluxo autenticado Zabbix → incidente no Hub → ticket GLPI, com isolamento de tenant, idempotência, auditoria e estado/frescor das fontes visíveis ao operador. Wazuh é pós-MVP e depende de aceite do MVP e aprovação de capacidade/custo. O plano mestre liga os oito critérios de aceite às tarefas e gates das Fases 0–4 e 6.

## Estado comprovado

| Frente | Estado | Base |
|---|---|---|
| Fase 0 / release | `FAIL` na última avaliação, de 26/09 | `docs/execution/gates/phase-0-recovery-release.md`; backup e restauração passaram, mas commit/digests, rollback e CI completo ainda bloqueiam release |
| Código local do Hub | Implementação em andamento | Fase 3 Task 1 concluída em `342a817`; workers falham fechado em `641a885`; a sonda `/ready` verifica PostgreSQL, esquema de incidente, Redis da aplicação e broker Celery, mas falta exercício do stack com containers reais |
| Identidade e tenant | Matriz inicial, gate pendente | Inventário de rotas em `docs/security/access-control-matrix.md`; HTTP e SSE revalidam papel, tenant e versão de sessão, e logout incrementa `session_epoch`; `operator`/`viewer` ainda não têm correspondência segura com papéis legados |
| MVP integrado | Não aceito | O detalhe restringe usuários de tenant; ações exigem papel NOC/SOC/admin, usam bloqueio de linha e persistem histórico. Ingestão e resolução registram incidente, ticket, falha GLPI e ACK Zabbix. `/webhook/zabbix` e `/v1/alerts` enfileiram o mesmo worker por evento. Recuperação Zabbix registra o sinal sem encerrar o ticket GLPI; ver `docs/operations/zabbix-recovery-policy.md`. O painel já distingue último sucesso, falha e dado desatualizado para Zabbix, Atera e GLPI; Wazuh aparece como planejado. Ainda faltam política final de papéis, validação do contrato em runtime real, fluxo integrado e gates das Fases 1–4 e 6 |
| Wazuh | Planejado | Fora do gate do MVP; sem compra ou rollout autorizado por este plano |

Os testes locais executados até aqui foram a suíte completa do backend (358 aprovados, dois avisos de depreciação), typecheck, lint e build do frontend, Ruff nos arquivos Python alterados e `bash infra/tests/test-aiops-runtime-readiness.sh`. O bootstrap SQL e a migração passaram na imagem PostgreSQL 16/TimescaleDB fixada pelo Compose; ver `docs/execution/evidence/local-hub-schema-bootstrap-2026-09-28.md`. Isso não substitui o exercício do stack real. Não houve nova coleta de saúde dos serviços ou de backups de produção nesta atualização. A evidência de 26/09 deve ser renovada antes de qualquer decisão de release.

## Próxima execução

1. Definir e testar o escopo de tenant do papel `operator` sem conceder acesso global de `noc`; manter a Fase 1 sem aprovação até o teste de isolamento passar em API e stream.
2. Provar a transição `unhealthy`/`healthy` da API e dos workers em ambiente com containers; os testes locais cobrem falhas de banco, Redis e broker, mas não o ciclo real do Docker.
3. Provar o fluxo Zabbix/GLPI de ponta a ponta, incluindo falha parcial e replay, e validar o stack completo; preservar a Fase 0 como gate para deploy e escritas em produção.
4. Reconciliar a release com os arquivos e imagens reais, CI e rollback antes de reavaliar a Fase 0.

A árvore da branch `feat/incidents-rbac-local` ainda contém alterações e arquivos não rastreados anteriores a esta atualização. Eles permanecem fora dos commits de implementação desta etapa.
