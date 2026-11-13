# Evidência — baseline da observabilidade de stack (V1)

Data: 12/11/2026

## Escopo

Comprovar a V1 de observabilidade proposta em `docs/superpowers/specs/2026-11-12-observabilidade-stack-ness-os-design.md`:

1. baseline das 3 VPS Contabo rastreadas;
2. payload consolidado de stack health;
3. cenário degradado controlado.

## Baseline das 3 VPS rastreadas

Referência canônica atual de inventário Contabo (read-only) permanece em:

- `docs/execution/evidence/phase-0-contabo-api-readonly-2026-09-25.md`

Stacks rastreadas pela V1:

| stack | display name | instance id | ip |
|---|---|---:|---|
| `aiops` | `aiops` | `203409271` | `144.91.115.242` |
| `zabbix-prod` | `ninfraops-zabbix` | `203409070` | `144.91.72.202` |
| `zabbix-prd-01` | `ness-os-zabbix-prd-01` | `203532557` | `169.58.234.9` |

### Tentativa de revalidação ao vivo em 12/11

Foi executada consulta read-only direta via `ContaboAPIClient` no container `ninf-api`, mas a autenticação ao `auth.contabo.com` retornou `400 Bad Request` no token endpoint.

Resultado: baseline de IDs/IPs mantida pela evidência de 25/09 até correção da credencial OAuth2.

## Payload consolidado (contrato)

A V1 implementa o endpoint agregado `GET /api/ops/stack-health` no router do dashboard.

Estrutura entregue:

- `summary`: totais por estado;
- `stacks[]`: estado consolidado por stack com causa e domínios;
- `domains`: payload bruto por domínio (`sources`, `contabo`, `pipeline`);
- `findings`: achados operacionais (ex.: provedor running + domínio crítico degradado/down).

Arquivos da implementação:

- `app/backend/app/services/stack_health.py`
- `app/backend/app/api/routers/dashboard.py`
- `app/backend/tests/test_stack_health.py`
- `app/backend/tests/test_stack_health_router.py`

## Cenário degradado controlado

Foi executado cenário sintético local chamando `build_stack_health_report` com:

- Contabo `running` para as 3 stacks;
- `zabbix` com `status=down`;
- `pipeline` com `status=degraded` (`workers_timeout`).

Saída resumida:

- `summary = { total: 3, ok: 1, degraded: 1, down: 1 }`
- findings inclui `runtime_issue_with_provider_running` para `aiops` e `zabbix-prod`.

Esse resultado comprova a regra central da V1: **`running` no provedor não mascara degradação real do serviço**.

## Limitações registradas

1. Revalidação online da Contabo bloqueada por credencial/token OAuth2 (HTTP 400 no auth endpoint).
2. Suite automatizada (`pytest`) não executada neste ambiente por ausência do pacote no Python local do runner.
