# Hub — fluxo local Zabbix → incidente → GLPI (2026-09-28)

**Escopo:** `tests/test_hub_local_flow.py` executado com PostgreSQL 16/TimescaleDB e Redis 7 descartáveis, usando os digests do Compose. Os scripts `000_init.sql`, `001_schema.sql` e `002_push_subscriptions.sql` prepararam o banco. Zabbix e GLPI foram simulados por `httpx.MockTransport`; o pipeline de negócio, o banco e a publicação Redis usaram código real. Nenhum sistema externo recebeu alerta ou ticket.

| Comportamento | Evidência local |
|---|---|
| Identidade do tenant | `host.get` retornou grupo `[ Cavan ]`; ticket solicitado na entidade GLPI 8 |
| Resposta perdida após criação | GLPI simulado criou ticket 501 e respondeu HTTP 502; o incidente foi persistido sem vínculo e com ação `ticket_failed` |
| Reentrega e replay | A busca pelo marcador encontrou o ticket 501; uma única criação, um incidente, `alert_count=1` e auditoria `ticket_reused` |
| Acesso por tenant | `viewer` de Cavan leu o incidente; pedido de outro tenant recebeu HTTP 403 |
| Recuperação Zabbix | Sinal `RESOLVED` atualizou `ninf_zabbix_status`; incidente e ticket permaneceram abertos para resolução pelo GLPI |
| Conteúdo do ticket | Campo HTML sintético foi escapado antes da criação |

Resultado: `1 passed, 1 warning` (aviso de depreciação de `datetime.utcnow`). Os containers foram removidos após o ensaio.

Para repetir, prepare um banco e um Redis **descartáveis** com os três scripts SQL, exponha ambos somente em `127.0.0.1` e execute no diretório `app/backend`:

```sh
NINF_LOCAL_FLOW_TEST=1 \
NINF_DATABASE_URL='postgresql+asyncpg://nessops:<senha-local>@127.0.0.1:<porta-pg>/nessops' \
NINF_REDIS_URL='redis://127.0.0.1:<porta-redis>/0' \
NINF_GEMINI_API_KEY= NINF_ALERT_NOTIFICATIONS_ENABLED=false \
python3 -m pytest tests/test_hub_local_flow.py -q
```

O teste recusa hosts de banco ou Redis fora de loopback e é ignorado na suíte normal.

Este teste verifica o fluxo de negócio com persistência e dependências locais. Ainda faltam a fila Celery e os endpoints HTTP reais no mesmo ensaio, UAT com Authentik/Zabbix/GLPI reais, concorrência e aprovação dos gates de release.
