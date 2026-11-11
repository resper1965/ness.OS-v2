# Promoção diária do Hub (API + workers)

Uma promoção por dia, com um lote de PRs. O ganho está em **juntar o lote** e **escolher o horário**: o script não pré-aquece backup (exige um com menos de 30 min e inicia outro se não houver).

Procedimento completo de release e rollback: [release-and-rollback.md](release-and-rollback.md). Script: `infra/scripts/aiops-promote-hub-api.sh`.

## Rotina

1. **Lote:** PRs mergeados na `main` até 14:00 entram na promoção do dia. O que chegar depois espera o dia seguinte.
2. **Publicar as imagens:** `POST /actions/workflows/publish-hub-images.yml/dispatches` com `{"ref":"main"}` (~2,5 min). Anote o digest da API (`ghcr.io/resper1965/ninf-api@sha256:…`) e o commit de 40 caracteres.
3. **Conferir o lote:** só tabelas aditivas (a migração roda uma vez, antes de trocar os serviços). Migração destrutiva ou incompatível com a versão anterior **não** entra no lote.
4. **Pedir a frase ao Ricardo**, dita com o efeito (modelo abaixo). "ok", "siga" e "aprovado" soltos não valem.
5. **Preparar o staging** na aiops, em `/tmp/stage-promo`: `docker-compose.yml` e `docker-compose.tickets.yml` do commit **e** `aiops-promote-hub-api.sh` do mesmo commit (`infra/scripts/`), todos copiados do checkout.
6. **Horário escolhido pelo Ricardo: 14h** (10/11). **Disparar logo depois do corte das 14:00** (entre ~14:00 e ~22:00, fora da janela do backup noturno das ~23:00). O script exige backup com menos de 30 min; sem ele, **inicia outro backup, que para GLPI e n8n por alguns minutos**. Avise quem usa o GLPI antes de disparar. Se preferir não parar o GLPI, dispare logo depois do backup noturno, ao custo de esperar o dia seguinte:
   ```
   sudo -n bash -c 'cd /tmp/stage-promo && nohup bash ./aiops-promote-hub-api.sh <sha40> <api-ref@sha256> /tmp/stage-promo > /tmp/promo-<sha7>.log 2>&1 < /dev/null & disown'
   ```
7. **Esperar** ~15–20 min. O script faz o canário `/ready`, troca API e workers e observa as tarefas de alerta por 5 min. Falha depois do canário restaura a release anterior sozinho.
8. **Registrar** em `docs/execution/evidence/hub-release-2026-10-26.md`: commit, digest da API, `backup_set`, release anterior, `promotion=PASS`, `hub_http`.

## Mensagem-modelo para a frase

> Promover `<sha7>` (tabelas aditivas: X; API: Y; frontend não incluso). Rollback: release `<anterior>`. Diga **promove**.

## O que o script não cobre

- **O canário não exercita a entrega de ticket.** Em 26/10 o `/ready` passou e 3.675 alertas falharam em 9 h. Por isso o script observa as tarefas reais por 5 min; **depois da promoção, confira `process_alert_v1` e os incidentes novos com ticket**.
- **Frontend, bancos, GLPI, Authentik e Caddy nunca são recriados** pelo script. O frontend tem procedimento próprio (troca da imagem no `.env`, com backup em `/opt/n-infraops/change-backups/`).
- **Mudança só de `.env` ou de imagem sem código novo** não precisa de promoção: edita-se o `.env` da release atual e de `/opt/n-infraops/app`, com backup, e recria-se só o serviço afetado.

## Rollback

O script imprime o comando ao fim (`rollback: docker compose -p app -f <release anterior>/docker-compose.yml … up -d --no-deps --force-recreate api worker-alerts worker-ml`). A release anterior continua em `/opt/n-infraops/releases/<sha>/app`. Migração aditiva é compatível com a versão anterior: não há migração reversa.

## Verificação (Task 5 do plano de aceleração)

Duas promoções consecutivas, em dias diferentes, com `promotion=PASS` e `ready=200`.

## Não promover

- Durante a janela de cutover do Zabbix.
- Com backup noturno falhando.
- Com lote que mexe em migração destrutiva, sem plano de restauração.
