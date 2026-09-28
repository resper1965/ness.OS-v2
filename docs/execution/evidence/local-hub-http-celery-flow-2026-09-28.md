# Hub — HTTP, Celery e persistência locais (2026-09-28)

**Escopo:** a imagem do backend foi construída do checkout `5d5e049` com o Dockerfile do projeto. API e worker de alertas rodaram em containers separados com PostgreSQL 16/TimescaleDB e Redis 7 descartáveis, usando os digests do Compose. O banco recebeu `000_init.sql`, `001_schema.sql` e `002_push_subscriptions.sql`. `infra/tests/hub_mock_services.py` serviu Zabbix JSON-RPC e GLPI HTTP na mesma rede Docker. A porta da API foi publicada apenas em `127.0.0.1:42571`. Notificações e Gemini ficaram desativados.

| Ensaio | Evidência |
|---|---|
| API e autenticação de máquina | `/ready` respondeu `200`; `POST /webhook/zabbix` sem chave respondeu `401`; com chave local respondeu `202` e enfileirou `alerts.primary` |
| Primeiro problema | Worker Celery consumiu a tarefa, fez `host.get` autenticado, escolheu entidade GLPI 8 (Cavan), criou ticket 501 e persistiu incidente 1 com `ticket_created` |
| Reentrega por outra rota | `POST /v1/alerts` para o mesmo evento retornou o mesmo fingerprint; o banco continuou com um incidente, `alert_count=1`, e o mock com um ticket para o evento |
| Resposta GLPI perdida | Para o segundo evento, o mock criou ticket 502 e devolveu HTTP 502. O worker persistiu `ticket_failed`, executou retry em 5 s, encontrou o ticket pelo marcador e registrou `ticket_reused` sem segunda criação |
| Recuperação | `POST /webhook/zabbix` com `RESOLVED` respondeu `202`; o worker registrou `zabbix_recovered`. O incidente 2 permaneceu `open`, vinculado ao ticket 502, com `ninf_zabbix_status=resolved` |
| Conteúdo HTML | O mock reportou `unsafe_html=false` para ambos os tickets com nome de host sintético contendo `<script>` |

Consulta final ao banco: **2 incidentes, 2 tickets, `alert_count=1` em ambos**. Histórico do incidente 2: `incident_created`, `ticket_failed`, `ticket_reused`, `zabbix_recovered`. Os cinco containers e a rede temporária foram removidos.

Este ensaio exercitou HTTP, autenticação por chave, broker, worker, APIs simuladas e persistência no mesmo fluxo. Não comprova Authentik, Zabbix ou GLPI reais, concorrência sob carga, UI humana nem o Compose completo no ambiente alvo. A Fase 0 permanece `FAIL` e não houve deploy ou escrita em produção.
