# Release do Hub — 26–27/10/2026 (Task 3.1)

## Resultado

API e workers em `412bdc0` desde 27/10 08:2x BRT. Frontend e demais serviços inalterados (release de 12/10).

| Item | Valor |
|---|---|
| Commit | `412bdc0d993b8cf6437af1964c75339c9b9b5ae7` (main, PR #95) |
| API | `ghcr.io/resper1965/ninf-api@sha256:31a99dc9460ec31dd7a830c480c8f48b76f68946ebc17d065fc9654a835dc8ec` |
| Frontend publicado (não promovido) | `ghcr.io/resper1965/ninf-frontend@sha256:b645447d332476ce7f82cbffadb8ca44b89c1d586d1f149025e7a950d46db4c6` |
| Workflow | `publish-hub-images.yml`, run `40494723069` |
| Backup antes | `20261027T081648-0300` (`COMPLETED`) |
| Release | `/opt/n-infraops/releases/412bdc0d993b8cf6437af1964c75339c9b9b5ae7/app` |
| Rollback | release `144317fd…` (comando no journal de `ness-hub-promote-412bdc0.service`) |
| Script | `infra/scripts/aiops-promote-hub-api.sh` (PR #86) |

Verificação após 5 min: `/ready` 200, Hub 200, 3 containers `healthy`, 0 restart, 0 traceback em API e `worker-ml`, `process_alert_v1` só `succeeded`.

## Incidente: promoção de 26/10 (`8cf3925`) revertida

- 26/10 23:10: promoção de `8cf3925` (API `26b6b6d9…`) → `PASS` (canário `/ready` e Hub 200).
- O canário não exercitou a entrega de ticket. Em 9 h, `worker-alerts` registrou 3.675 falhas `GLPI omitiu Content-Range da busca` e 235 `Cliente sem entidade GLPI mapeada` (esta já existia antes); nenhum alerta virou ticket novo.
- Causa: o GLPI de produção responde busca vazia com `200`, `[]` e **sem** `Content-Range` (medido em 27/10, só leitura: busca sem resultado → 200 sem header; com resultado → 206 `0-99/284`). A paginação nova exigia o header. O fake do teste devolvia `*/0`, que o GLPI real não manda.
- 27/10 ~08:05: rollback manual para `144317fd…` (comando do próprio script); `process_alert_v1` voltou a `succeeded`.
- Correção: PR #95 (primeira página vazia sem `Content-Range` = coleção vazia; teste com a resposta real). Imagens republicadas da `main` e promovidas pelo mesmo script.
- Alertas do período: os que falharam esgotaram retry ou ficaram registrados; reconciliar pelo `glpi_backlog_classify.py` (Task 2.4 Step 4).

## Lição

O canário da promoção precisa exercitar a entrega de ticket, não só `/ready`: após promover, contar `process_alert_v1` por resultado por alguns minutos e reverter se houver falha nova. Pendente no script (PR #86).
