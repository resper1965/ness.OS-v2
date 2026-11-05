# Release do Hub — 26–27/10/2026 (Task 3.1)

## Resultado

API e workers em `3b7e7cb` desde 05/11/2026 (antes: `fa4f2a9` 05/11, `9992bf7` 04/11, `56c4659`, `521247b` 30/10, `7e7dfc6` 28/10 16:45 BRT, `3651780` 28/10 08:40, `9c34eda` 27/10 19:10, `412bdc0` 27/10 08:2x; a tabela abaixo é da `412bdc0`, as demais estão no fim). Frontend e demais serviços inalterados (release de 12/10).

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

## Promoção de `c16471d` (03/11) — triagem SOC aprovada

#136 (`GET /api/secops/archived-sample`, índice `(action_taken, created_at)`) e #137 (cartão de triagem). API e workers em `ghcr.io/resper1965/ninf-api@sha256:211aaf9c4cc2d61e77ed5db0722f8b12dba2920f9fb6c421de7727122514197a`; frontend em `ghcr.io/resper1965/ninf-frontend@sha256:1051d84ff41f27cefed0e8ee2db1ff259282c51a3b3be15c9048a6bd569558f8` (`publish-hub-images`, commit `c16471d`). `promotion=PASS`, 15 alertas ok, 0 falhas; `/api/assets` e `/api/secops/archived-sample` 401 sem sessão. Rollback: release `521247b` (API/workers) e frontend `604e9b9…`.

**Tentativa anterior (`d937141`) revertida sozinha pelo script.** O build novo resolveu `kombu 5.7.0` (celery 5.4 aceita `>=5.3,<6`), que exige `redis-py >= 6.1`; a imagem tem 5.3.1 e os dois workers reiniciavam com `VersionMismatch`. O rollback automático restaurou a release anterior, saudável, em ~10 min. Correção: pin `kombu==5.6.*` (#142). Lição: dependência transitiva sem lockfile faz o build do mesmo código diferir do que está em produção; vale congelar o resultado do `pip` (lockfile) no futuro.

Frontend: a primeira troca devolveu 502 (o Caddy ainda não alcançava o contêiner novo) e o script reverteu; a segunda, com espera pelo `/` responder, passou.

## Promoção de `56c4659` (04/11) — P0 Fundação SOC

#147: atendimento por função própria, `pendente_de_cliente`, validação com campo/valor/sinal no log, prazo de 45 s no modelo, frequência persistida por tenant + cluster (`freq_key`). API e workers em `ghcr.io/resper1965/ninf-api@sha256:235ef1b81e555cc0c3d5ddc934b287c24a7d660790547465602df2e6416815f9`; frontend inalterado (`1051d84ff41f`, sem mudança de compose).

`aiops-promote-hub-api.sh` com canário de 300 s: `promotion=PASS`, backup `20261104T074026-0300` (rodou o backup noturno, ~10 min). `migrate.py` criou `n_secops_soc_decisions.freq_key` e o índice `ix_soc_decisions_freq`. Verificado: `ready=200`, API e workers saudáveis, 0 erros nos logs do worker, `/api/secops/triage` 401 sem sessão, frontend 200, 45 eventos de incidente nos 10 min seguintes. Nenhuma integração Wazuh → Hub ativada.

Rollback: release `c16471d` (`docker compose -p app -f /opt/n-infraops/releases/c16471ddeedad4a8cd03103441652696fefa64b1/app/docker-compose.yml -f …/docker-compose.tickets.yml up -d --no-deps --force-recreate api`, mais workers). A coluna `freq_key` é aditiva e nullable: a versão anterior a ignora.

## Promoção de `9992bf7` (04/11) — urgência/impacto no GLPI e fila/timeline

#158 (Hub envia `urgency` e `impact` ao GLPI conforme a severidade Zabbix; ausente, inválida ou 0 fica em 3), #161 (fila por prioridade, filtros, `ticket_state`, `/timeline`, `X-Request-ID`), #159/#160/#163 (documentação e contrato). API e workers em `ghcr.io/resper1965/ninf-api@sha256:7e55141bdec998fb1ba39bdb24706ed69de46bb9161b30305714ea3151031af9` (`publish-hub-images` run 41898439132). Frontend inalterado. Sem migração.

`aiops-promote-hub-api.sh`: `promotion=PASS`. Verificado: `ready=200`, API e workers saudáveis, 0 erros na API; 17 incidentes novos em 15 min, todos com ticket. Tickets GLPI dos últimos 40 min: 68 com urgência/impacto 3 e 1 com 2/2, ou seja, a severidade chega ao GLPI. Seis `ReadTimeout` do GLPI no worker, todos reagendados em 900 s pela idempotência (sem ticket duplicado). Nenhuma integração Wazuh → Hub ativada.

Rollback: release `56c4659` (`docker compose -p app -f /opt/n-infraops/releases/56c46594deea281392cfcc39a30ab20d6faeff19/app/docker-compose.yml -f …/docker-compose.tickets.yml up -d --no-deps --force-recreate api`, mais workers).

## Promoção de `3b7e7cb` (05/11) — modalidade por cliente e frescor por fonte

#164 (decisão SOC vinculada ao incidente na linha do tempo), #166 (frescor e cobertura por fonte em `pipeline-status`), #167/#168 (`modality` e `operator` em `n_infraops_tenant_mappings`, nomes `managed`, `onsite`, `shared`). API e workers em `ghcr.io/resper1965/ninf-api@sha256:bb7a3800fb3d08d0caf9b9a347b9739c2ba2244ece1377845de3dea5fbe38fb6` (`publish-hub-images` run 42018737432). Frontend inalterado. Migrações aditivas: `incident_id`, `modality`, `operator`, índices `ix_soc_decisions_created` e `ix_soc_decisions_incident`, `CHECK ck_tenant_mappings_modality` com os nomes novos. Uma promoção intermediária (`fa4f2a9`) criou o `CHECK` com os nomes antigos; a migração de `3b7e7cb` o recriou sem linhas afetadas.

`aiops-promote-hub-api.sh`: `promotion=PASS`. Verificado: `ready=200`, API e workers saudáveis, 0 erros nos logs.

Registro (OK do Ricardo em 05/11): `UPDATE n_infraops_tenant_mappings SET modality='managed'` nos 9 vínculos `wazuh` (ids 1–9). Rollback: `UPDATE ... SET modality=NULL WHERE id BETWEEN 1 AND 9`. Efeito em `pipeline-status`: Wazuh passa a `coverage_declared=true`; Zabbix continua `pendente_de_modalidade` porque não há vínculo dele em `n_infraops_tenant_mappings`. O Wazuh aparece com `stale=true` e `reason=sem_dados` (nenhuma decisão SOC gravada), o que é o estado real: nada chama `/secops/triage` em produção.

Rollback da API: release `fa4f2a9` (`docker compose -p app -f /opt/n-infraops/releases/fa4f2a9ba9b0b74fbdeb7d8c26a5f00aeaf7be8d/app/docker-compose.yml -f …/docker-compose.tickets.yml up -d --no-deps --force-recreate api`, mais workers).
