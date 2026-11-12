# Gate — Stack Observability V1

Data: 12/11/2026
Escopo: endpoint consolidado + visão por stack + evidência mínima de baseline

## Resultado

**Status geral: FAIL (condicional)**

A V1 está implementada em código, mas o gate permanece `FAIL` até fechar as pendências de validação operacional online.

## Itens do gate

| Item | Status | Evidência |
|---|---|---|
| Endpoint `GET /api/ops/stack-health` implementado | PASS | `app/backend/app/api/routers/dashboard.py` |
| Consolidação de estado por stack (`ok/degraded/down`) | PASS | `app/backend/app/services/stack_health.py` |
| Find­ing “provider running + runtime degraded/down” | PASS | `app/backend/tests/test_stack_health.py` + evidência de cenário controlado |
| Painel frontend por stack integrado ao CoreDashboard | PASS | `app/frontend/src/components/StackHealthPanel.tsx`, `CoreDashboard.tsx` |
| Baseline das 3 VPS rastreadas documentado | PASS | `docs/execution/evidence/stack-health-baseline-2026-11-12.md` |
| Revalidação online Contabo em 12/11 | FAIL | autenticação OAuth2 com HTTP 400 no token endpoint |
| Execução de testes automatizados no ambiente deste runner | FAIL | `pytest`/`npm` indisponíveis localmente |

## Pendências para virar PASS

1. Corrigir credenciais da integração Contabo e repetir coleta read-only ao vivo.
2. Rodar testes backend/frontend em ambiente com toolchain completo e anexar saída.
3. Capturar uma chamada real de `/api/ops/stack-health` após deploy/canário interno.

## Decisão operacional

Não bloqueia desenvolvimento local, mas **bloqueia declarar observabilidade V1 homologada** até fechar as três pendências acima.
