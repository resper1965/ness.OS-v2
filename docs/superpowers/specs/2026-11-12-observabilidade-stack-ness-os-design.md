# Desenho — Observabilidade da stack ness.OS

**Status:** proposta aprovada para execução
**Data:** 12/11/2026
**Escopo:** observabilidade operacional de VPS, serviços e integrações do ness.OS, com foco em decisão rápida de operação e contratação.

## Objetivo

Dar ao operador uma visão única e confiável do estado da stack, separando claramente:

1. **Control plane** (Contabo API): inventário, estado da instância, snapshots, rede/firewall;
2. **Data plane** (dentro da VPS): disponibilidade real de serviço, filas, erros, latência e frescor da coleta.

Sem essa separação, `running` no provedor vira falso positivo de saúde.

## Problema que resolve

- Hoje já existem endpoints úteis (`/api/dashboard/sources`, `/api/contabo/*`, `/api/dashboard/pipeline-status`), mas sem uma visão consolidada por stack.
- O operador ainda cruza fontes manualmente para responder: “a VPS caiu?”, “o serviço caiu com VPS de pé?”, “backup está vencido?”, “qual risco operacional agora?”.

## Decisões de design

1. **Reuso primeiro:** não criar nova plataforma; consolidar em cima das rotas e serviços já existentes.
2. **Read-only no provedor:** Contabo continua somente leitura.
3. **Contrato único por domínio:** cada fonte publica `{status, source, observed_at, last_success_at, freshness_seconds, stale, error_code, data}`.
4. **Fail-closed de frescor:** falha de coleta nunca atualiza `last_success_at`.
5. **Estados explícitos:** `ok`, `degraded`, `down`, `planned`, `unavailable`.
6. **Tenant e RBAC preservados:** sem quebrar isolamento existente; endpoints operacionais continuam `noc`/`platform_admin` conforme sensibilidade.

## Não objetivos

- Não executar ações mutáveis na Contabo (start/stop/restart/resize/firewall mutate).
- Não substituir Zabbix como monitor de métrica interna.
- Não expandir para FinOps completo nesta etapa.

## Modelo funcional

### Domínios iniciais

- **infra_contabo**: inventário VPS, status, snapshots, rede/firewall (control plane).
- **runtime_hub**: API/worker/redis/postgres/pipeline (data plane).
- **sources_ops**: Zabbix, GLPI, Atera, Wazuh(planned) já expostos em `/api/dashboard/sources`.
- **backup_posture**: idade do último backup válido por stack crítica.

### Visão agregada (novo endpoint)

`GET /api/ops/stack-health`

Retorna:

- `summary`: total de stacks por estado e riscos críticos;
- `stacks[]`: para cada stack (`zabbix-prod`, `aiops`, `zabbix-prd-01`), estado consolidado, causa e evidências curtas;
- `domains`: payload bruto normalizado por domínio;
- `findings`: lista curta de violações operacionais (snapshot vencido, serviço down com VPS running, recurso órfão sem monitoramento).

## Regras de consolidação

1. Se qualquer domínio crítico estiver `down` => stack `down`.
2. Se não há `down`, mas há `degraded`/`stale` => stack `degraded`.
3. Se todos críticos `ok` => stack `ok`.
4. `planned` e `unavailable` não derrubam stack por si só, mas entram em findings quando obrigatórios por contrato.

## SLO operacional (inicial)

- Coleta control plane Contabo: até **5 min** de frescor.
- Coleta runtime/data plane: até **2 min** de frescor.
- Snapshot/backup posture: atualização até **15 min**.
- Tempo de resposta do endpoint agregado: p95 **< 2s** com cache curto.

## Segurança e auditoria

- Sem credenciais de provedor no frontend.
- Redação de erros de provedor (`Contabo API indisponível`, sem vazamento de detalhes sensíveis).
- Log estruturado por `source`, `status`, `error_code`, `freshness_seconds`.

## Dependências e riscos

- Dependência da API Contabo para control plane.
- Risco de “saudável parcial” se não houver prioridade de domínio bem definida.
- Inconsistência de cadastro/mapeamento de clientes (ex.: chaves operacionais ativas fora do cadastro canônico) pode distorcer visão por tenant.

## Critérios de aceite

1. Operador vê estado consolidado por stack sem abrir múltiplas telas.
2. Casos “VPS running + serviço down” aparecem como `degraded/down` com causa explícita.
3. Falha de coleta mantém último sucesso e marca `stale`.
4. Testes de contrato e RBAC passam.
5. Endpoints read-only de Contabo permanecem sem métodos mutáveis expostos.

## Resultado esperado

Com esse desenho, a decisão “contrata nova VPS agora ou reaproveita a existente?” deixa de ser opinião e passa a usar sinais operacionais consistentes, com fonte e frescor auditáveis.
