# F2 da IA nos chamados — aviso à operação

**Conclusão:** com `NINF_ZABBIX_REPEAT_FOLLOWUP_ENABLED=true`, o mesmo trigger no mesmo host com chamado aberto entra como acompanhamento desse chamado, e não gera um chamado novo.

Status: **não promovida; flag desligada por padrão.** Ligar só após este aviso e o OK do Ricardo.

## O que muda para quem atende

- **Acompanhamento:** repetição do mesmo trigger no mesmo host, com chamado aberto, vira acompanhamento do chamado raiz.
- **Web Push:** continua igual. Repetição com severidade de origem HIGH/CRITICAL ainda dispara push.
- **Solução no GLPI:** resolve a raiz e as repetições.
- **Raiz resolvida ou fechada:** nunca é reaproveitada; novo alerta abre chamado novo.
- **Tela "IA":** card "Sinais ÷ chamados" (sinais, chamados e repetições na janela).

## Para quem opera o Hub

- **Antes de ligar:** rodar [ai-f2-tempestade.sql](ai-f2-tempestade.sql) (`psql -f`, conta só de leitura) e anexar o resultado.
- **Migração:** aditiva (`python -m app.migrate`): coluna `repeat_of_id` e índice em `n_infraops_incidents`.
- **Rollback:** desligar a flag; coluna e índice podem ficar.
