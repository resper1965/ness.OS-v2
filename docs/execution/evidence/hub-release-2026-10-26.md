# Release do Hub — 26–27/10/2026 (Task 3.1)

## Resultado

API e workers em `7e7dfc6` desde 28/10 16:45 BRT (antes: `3651780` 28/10 08:40, `9c34eda` 27/10 19:10, `412bdc0` 27/10 08:2x; a tabela abaixo é da `412bdc0`, as demais estão no fim). Frontend e demais serviços inalterados (release de 12/10).

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
- Reconciliação (27/10, consulta só leitura em `n_infraops_incidents`, janela 26/10 23:10 – 27/10 08:10 BRT):
  - 753 incidentes criados; 14 com ticket (busca não vazia) e **739 sem ticket**, todos `open`, última ação GLPI `ticket_failed error=RuntimeError`;
  - 739 eventos Zabbix distintos, 88 hosts, 65 títulos; nenhum recebeu alerta depois de 08:10;
  - 524 têm incidente posterior com o mesmo título e host que já ganhou ticket após a correção; **215 não têm ticket algum**.
  - Não há retry pendente: o Celery registrou `raised unexpected`. Recriar os tickets é escrita no GLPI de cliente e espera decisão (Task 2.4 Step 4).

## Lição

O canário da promoção precisa exercitar a entrega de ticket, não só `/ready`: após promover, contar `process_alert_v1` por resultado por alguns minutos e reverter se houver falha nova. O PR #86 acrescenta essa verificação ao script (falhas+retries acima dos sucessos desde o recreate → rollback) e passa a sondar a API pelo Caddy (`/api/assets` → 401), já que `/` é o frontend.

## Replay dos alertas ainda ativos (27/10, ~17:22 BRT, OK do Ricardo)

Dos 215 incidentes sem ticket, 26 tinham o mesmo problema ainda ativo no Zabbix (mesmo `event_id`, fingerprint idêntico). Reenfileirados pelo pipeline normal (`process_alert_v1`, fila `alerts.primary`) só os 12 de FortiGate (latência ICMP e sem coleta SNMP). Resultado: 12/12 com ticket, 12 tickets distintos, nenhum ticket compartilhado entre incidentes. Os outros 14 ativos (Google Updater parado em servidores Windows e espaço de disco em `alpdb01`/`alpdb02`) ficaram sem replay, aguardando decisão. Os 189 restantes já se resolveram e ficam sem ticket.

## Avaliação do processo

- **Canário sem ticket:** a promoção só olhava `/ready` e Hub 200, não exercitava a entrega de ticket. Corrigido no PR #86 (falhas+retries acima dos sucessos desde o recreate → rollback).
- **Fake divergente do GLPI real:** o fake devolvia `Content-Range: */0` em busca vazia; o GLPI real responde `200` sem o header. Corrigido no PR #95. Recomendação: teste de contrato contra `infra/tests/glpi-lab`, para o fake não divergir de novo.
- **Monitor sempre vermelho:** `hub-integration-monitor.sh` falhava toda execução (backlog histórico sem ticket e contador cumulativo de falhas), então ninguém olhava e 9 h passaram sem reação. Este PR limita o sinal a incidentes abertos sem ticket entre 5 e 60 min e a falhas dos últimos 15 min. A rota de notificação (canal) segue pendente: decisão do Ricardo.
- **Sem replay para `ticket_failed`:** nada reenfileirava os incidentes sem ticket. Script versionado neste PR: `infra/scripts/glpi_ticket_replay.py` (dry-run por padrão, só incidente aberto sem ticket com fingerprint idêntico).
- **Ruído Google Updater (12 alertas):** ajuste do trigger no Zabbix depende de GO (D5).

## Promoção de `9c34eda` (27/10 ~19:10 BRT)

Monitor acionável (#111): API e workers em `ghcr.io/resper1965/ninf-api@sha256:5ed418b49ab2d4958f73193d5ed2b4109bed0739530333b16549421c89df9124` (`publish-hub-images` run 40590782395). Script `aiops-promote-hub-api.sh` → `promotion=PASS`, canário de alertas sem falha, `/api/assets` 401, 3 contêineres `healthy` e 0 restart. Backup prévio `20261027T190327-0300`. `pipeline_health` passou a dar `ok` (rc=0): `workers failures:0`, `delivery: sem ticket entre 5 e 60 min: 0`. Em 5 min, 0 execuções do monitor com falha, a primeira vez que fica verde. Rollback: release `412bdc0` (comando no journal de `ness-hub-promote-9c34eda`).

## Entidade Unimed no GLPI (28/10, OK do Ricardo)

O monitor novo acusou alertas recusados com "Cliente sem entidade GLPI mapeada": hosts dos grupos `[ Unimed ]` (Itu e Salto) no Zabbix, sem entidade no GLPI. Criada com `infra/scripts/glpi-entity-create.php` (dry-run, `--apply`, reexecução idempotente): entidade 12 "Unimed" sob a raiz, vínculo da 94 (perfil 12, não recursivo) id 126 e grupo técnico `infraops/NOC` id 28, no padrão das demais. Hub mapeia `Unimed` → 12. Rollback: remover o mapeamento e a entidade 12 (sem tickets nela antes deste PR).

## Promoção de `3651780` (28/10 ~08:40 BRT)

Mapeamento Unimed → 12 e CMDB cobrindo a entidade 12 (#115). API e workers em `ghcr.io/resper1965/ninf-api@sha256:fdc3470bf1d8fb180f5fc34c59dada83f8fa21d35bac2af93df2bd8c5005452d` (`publish-hub-images` run 40678184116). `promotion=PASS`, `/api/assets` 401, 3 contêineres `healthy`, 0 restart; backup prévio `20261028T082159-0300`. Primeiro alerta Unimed pós-promoção virou ticket na entidade 12; 0 recusas "Cliente sem entidade" em 15 min. As recusas anteriores não criaram incidente (falham antes), então não há replay: o próximo evento de cada problema ativo abre o ticket. Rollback: release `9c34eda` (comando no journal de `ness-hub-promote-3651780`).

## Promoção de `7e7dfc6` (28/10 ~16:45 BRT) — LLM via OpenRouter

Gemini direto dava 429 (cota gratuita) em 134/135 análises. #117 troca os três pontos (análise de incidente, triagem Wazuh, pós-incidente) por `app/integrations/llm.py` no OpenRouter (`google/gemini-2.5-flash`, `data_collection: deny`, `require_parameters` com schema). Chave própria do Hub, limite US$ 50/mês com reset mensal, em `NINF_LLM_API_KEY` no `.env` da release (root 0600; cópia anterior em `/root/rollback-mail/env-before-llm`). Imagem `ghcr.io/resper1965/ninf-api@sha256:3633686e18b52d68cf0fbc6830c1c5a4c79b25f9f309134cdfcff2c577e7f5c7` (run 40725803751), `promotion=PASS`, `/api/assets` 401, 3 contêineres `healthy`, 0 restart, backup `20261028T133502-0300`. Pós-promoção: `ai_call incident_analysis outcome=ok`, ~2,6 s, ~560 tokens de entrada e ~320 de saída por análise. Embedding segue no Gemini (`ponytail:`). Rollback: release `3651780`.

## Promoção de `521247b` (30/10) — fundação SOC e idempotência do triage

#122 (cliente por vínculo, atendimento independente do score, `PENDING_REVIEW`) e #125 (idempotência de `/secops/triage`). API e workers em `ghcr.io/resper1965/ninf-api@sha256:d5120e8999887be0410b36a676c72228586a2d6f90db853a70b198a06615d168` (`publish-hub-images` run 41087515162). `promotion=PASS`, 3 contêineres `healthy`, `/api/assets` 401. Migração em produção conferida só leitura: `customer_id` anulável, `dedup_key` criada, `uq_soc_decisions_dedup` único parcial, 0 linhas na tabela. Rollback: release `7e7dfc6`. Nenhuma integração Wazuh → Hub ativada.
