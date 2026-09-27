# ness.OS Full Operationalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levar o ambiente atual do ness.OS a um estado operacional comprovado, com recuperação testada, identidade e isolamento validados, Zabbix e GLPI saneados, Hub confiável, dashboard fiel às fontes e Wazuh incorporado quando o gate de contratação for atendido.

**Architecture:** O Hub continua como plano de integração e experiência operacional. Zabbix, GLPI, Authentik, Psono, n8n, Contabo e Wazuh permanecem sistemas de registro de seus domínios; o Hub consome seus contratos, expõe saúde e frescor e nunca converte indisponibilidade em sucesso. Cada fase produz evidência, rollback e um gate que bloqueia dependências posteriores.

**Tech Stack:** Docker Compose, systemd, Bash, Python/FastAPI, Celery, Redis, PostgreSQL, React/Vite, Authentik/OIDC, Zabbix 7.0, GLPI, Psono, Contabo API, Restic/S3 e Wazuh 4.14.7.

**Spec:** `docs/architecture/ness-os-official-architecture.md`; avaliação de entrada em `docs/evaluations/ness-os-system-review-2026-09-17.md`; desenho do Wazuh em `docs/superpowers/specs/2026-09-18-wazuh-production-entry-design.md`.

## Global Constraints

- Preservar mudanças locais existentes; cada commit deve incluir somente os arquivos enumerados na tarefa.
- Não aplicar alterações diretas no banco de produção. Usar APIs, migrações versionadas ou ferramentas oficiais.
- Não registrar tokens, senhas, cookies, chaves, dumps ou conteúdo de segredos em logs e evidências.
- Executar primeiro em modo somente leitura ou dry-run; toda escrita em produção exige escopo, rollback e evidência anterior.
- Manter notificações externas desabilitadas durante testes sintéticos até o gate final.
- Toda métrica exibida no dashboard deve trazer fonte, instante de coleta, estado de frescor e erro explícito.
- Componentes ainda não implantados devem aparecer como `planned` ou `unavailable`, nunca como saudáveis.
- Usar a API da Contabo inicialmente somente para inventário, estado e reconciliação. Usar Object Storage da Contabo via S3/Restic com criptografia e bucket separado por domínio.
- A contratação do Wazuh ocorre somente após o aceite do MVP, aprovação explícita de orçamento e gate pós-MVP de capacidade/custo; preparação local de código e documentação pode ocorrer antes.
- Evidência operacional deve conter comandos, horários em UTC, resultado e referência da release, sem dados sensíveis.

---

## Estado de entrada confirmado em 2026-09-18

| Frente | Estado | Implicação |
|---|---|---|
| Hub/API/workers/Postgres/Redis | Serviços ativos e sondas privadas aprovadas | Pode ser refinado em voo, com rollout reversível |
| Backup do Hub | Falha recorrente por ausência de `docker0`; último conjunto completo em 2026-09-07 | Bloqueia mudanças de maior risco |
| Zabbix 7.0.27 | Operante com 259 hosts, mas backup local e remoto desabilitado e último conjunto em 2026-08-30 | Recuperação e saneamento são prioridade |
| Zabbix qualidade | 1.967 itens não suportados, 899 triggers desconhecidas, 240 hosts sem tags, 15 sem template e 1.321 problemas ativos | O dashboard não pode tratar o total bruto como saúde confiável |
| GLPI | Integração dry-run aprovada | Pode receber catálogo e teste sintético controlado |
| Authentik | Rotas públicas e SSO básico aprovados | Falta matriz completa de sessão, MFA, revogação e break-glass |
| Psono | Aplicação e backup saudáveis | MFA, recovery codes e emergency access ainda incompletos |
| Release | Produção sem checkout e árvore local com mudanças não consolidadas | Falta vínculo reproduzível entre código e runtime |
| Dashboard | Funciona, mas pode mostrar fonte conectada após erro e contém dados estáticos de segurança | Precisa de contrato de verdade operacional |
| Wazuh | Não implantado; DNS ausente; inventário Ansible obsoleto | Seguir pacote próprio depois do gate de compra |

## Sequência e dependências

```mermaid
flowchart LR
    P0[Fase 0<br/>Recuperação e release] --> P1[Fase 1<br/>Identidade e tenants]
    P0 --> P2[Fase 2<br/>Zabbix e GLPI]
    P0 --> P3[Fase 3<br/>Hub confiável]
    P1 --> P4[Fase 4<br/>Dashboard operacional]
    P2 --> P4
    P3 --> P4
    P0 --> WPREP[Preparação Wazuh sem compra]
    P4 --> P6[Fase 6<br/>Aceite integrado do MVP]
    P6 --> P5[Fase 5<br/>Wazuh pós-MVP]
    WPREP --> P5
    P1 --> P6
    P2 --> P6
    P3 --> P6
```

## Planos por fase

| Fase | Plano | Gate de saída |
|---|---|---|
| 0 | `docs/superpowers/plans/2026-09-18-phase-0-recovery-release-baseline.md` | Backups recentes e restaurações aprovadas; release identificável e reversível |
| 1 | `docs/superpowers/plans/2026-09-18-phase-1-identity-tenant-controls.md` | Matriz de acesso, MFA, revogação e isolamento aprovados |
| 2 | `docs/superpowers/plans/2026-09-18-phase-2-zabbix-glpi-operations.md` | Fontes confiáveis e fluxo alerta-incidente-ticket idempotente |
| 3 | `docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md` | Saúde do runtime mede os componentes reais e rollout é reproduzível |
| 4 | `docs/superpowers/plans/2026-09-18-phase-4-dashboard-operational-truth.md` | Dashboard completo para o escopo implantado, com erro e frescor honestos |
| 5A — pós-MVP | `docs/superpowers/plans/2026-09-18-wazuh-4147-production-rollout.md` | Após aceite do MVP e gate aprovado de capacidade/custo, Wazuh 4.14.7 instalado, recuperável e estabilizado em ondas |
| 5B — pós-MVP | `docs/superpowers/plans/2026-09-18-wazuh-security-signal-ingestion.md` | Após aceite do MVP, sinais Wazuh chegam ao Hub sem duplicação e com compatibilidade para Wazuh 5 |
| 6 | `docs/superpowers/plans/2026-09-18-phase-6-integrated-acceptance.md` | Operação ponta a ponta aprovada e sustentada por sete dias |

## Entrega do MVP

O MVP é o fluxo autenticado de operação Zabbix → incidente Hub → ticket GLPI, com isolamento por tenant, saúde/frescor reais e interface do operador. O Wazuh permanece planejado e não bloqueia o aceite do MVP. O desenho e a sequência executável estão em [`2026-09-27-ness-os-mvp-delivery-and-evolution-design.md`](../specs/2026-09-27-ness-os-mvp-delivery-and-evolution-design.md) e [`2026-09-27-ness-os-mvp-delivery.md`](2026-09-27-ness-os-mvp-delivery.md).

| Critério de aceite do MVP | Plano e tarefas responsáveis | Gate |
|---|---|---|
| Alerta Zabbix cria incidente Hub e ticket GLPI vinculado | Fase 2 Tasks 4–5; Fase 6 Tasks 2–3 | Gates 2 e 6 |
| Redelivery e retry não duplicam incidente ou ticket | Fase 2 Task 4; Fase 3 Task 3; Fase 6 Task 3 | Gates 3 e 6 |
| Papel/tenant bloqueia leitura ou escrita fora do escopo, também na API | Fase 1 Tasks 1, 4 e 6; Fase 6 Task 2 | Gates 1 e 6 |
| Falha de fonte/worker/GLPI mostra erro e última coleta válida | Fase 3 Tasks 1–2; Fase 4 Tasks 1 e 3; Fase 6 Task 3 | Gates 3, 4 e 6 |
| Mudança de estado, atribuição e ação de integração tem auditoria | Fase 2 Task 4; Fase 6 Tasks 1–3 | Gate 6 |
| Testes críticos, build frontend e lint passam na candidata | Gates das Fases 1–4; Fase 6 Task 5 | Gates 1–4 e 6 |
| Release identifica commit/imagens e comprova backup/restore/rollback | Fase 0 Tasks 1–5; Fase 3 Task 4; Fase 6 Task 4 | Gates 0, 3 e 6 |
| Aceite de produção exige gates aprovados das Fases 0–4 | Fases 0–4; Fase 6 Task 5 | Gate 6 |

## Regras de execução do programa

- [ ] Registrar o início de cada fase em `docs/execution/ness-os-operationalization-log.md`, com responsável, janela, release e rollback.
- [ ] Aprovar a Fase 0 antes de qualquer alteração de produção em esquema, autenticação, roteamento, provisionamento ou release; implementação e testes locais podem avançar antes desse gate.
- [ ] Após a Fase 0, promover Fases 1, 2 e 3 em sequência de gates; desenvolvimento local pode ocorrer em paralelo somente quando os contratos e os serviços não colidirem.
- [ ] Desenvolver e testar localmente a Fase 4 quando os contratos locais das Fases 1, 2 e 3 estiverem estáveis; bloquear seu deploy até os três gates de produção aprovados.
- [ ] Obter cotação da VPS e Object Storage somente após estimar retenção com dados das fontes reais.
- [ ] Contratar a VPS do Wazuh somente após aceite do MVP, aprovação explícita do orçamento e gate pós-MVP de capacidade/custo.
- [ ] Executar o aceite integrado com módulos ausentes explicitamente marcados; nenhum módulo planejado bloqueia o escopo já contratado se estiver isolado e descrito.
- [ ] Encerrar o programa somente com evidências de backup, restauração, autenticação, tenant, idempotência, observabilidade, rollback e operação por sete dias.

## Definição global de operacional

- [ ] Um operador autenticado vê estado, fontes, incidentes, ativos, tickets e backups autorizados para seu tenant.
- [ ] Uma falha de fonte aparece como falha ou dado obsoleto com horário da última coleta válida.
- [ ] Um alerta repetido não abre incidentes ou tickets duplicados.
- [ ] A revogação de sessão e a troca de papel passam a valer também em conexões de longa duração.
- [ ] Backups locais e externos respeitam RPO de 24 horas e têm restauração automatizada comprovada.
- [ ] Cada host monitorado possui tenant, tags, template e vínculo de inventário coerentes.
- [ ] Cada release em produção aponta para commit, imagens, configuração versionada e procedimento de rollback.
- [ ] Wazuh, quando contratado, opera em infraestrutura dedicada e entra por ondas de 5, 25 e até 50 endpoints.
- [ ] A equipe consegue executar os runbooks sem conhecimento implícito do autor da implementação.
