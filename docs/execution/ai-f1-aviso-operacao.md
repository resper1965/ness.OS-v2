# F1 da IA nos chamados — aviso à operação

**Conclusão:** a partir da promoção, o Web Push de alerta sai só pela severidade do Zabbix (≥ 4, HIGH/CRITICAL). A IA não escala mais. Divergências aparecem na tela "IA".

Status: **não promovida**. Enviar este aviso antes; promoção com OK do Ricardo.

## O que muda para quem atende

- **Push:** só dispara quando a severidade de origem no Zabbix é ≥ 4. Antes, a IA podia subir a urgência e disparar push.
- **IA não escala:** ela deixa de subir urgência, e `isolation_required` não gera mais push.
- **Rótulo de severidade** no Web Push e no Loki passa a vir da origem, não da IA.
- **Tela "IA"** (`?view=ai`): métricas, retorno "útil" do analista e divergências (motor × modelo no SOC).
- **Cliente:** o formulário de edição ganhou a caixa "IA externa permitida" (desmarcar = nada do cliente vai ao modelo externo: análise NOC/SOC e pós-incidente são puladas, e o relatório avisa).
- **Chamado no GLPI:** o corpo mostra "Opinião da IA (urgência)", que pode ser menor que a severidade de origem; a urgência do chamado continua vindo do Zabbix.

## Para quem opera o Hub

- **Variável nova:** `NINF_AI_BUDGET_ALERT_EMAIL` (e-mail que recebe o alerta do teto mensal; um por mês). O alerta só sai com e-mail transacional ligado (`NINF_TRANSACTIONAL_EMAIL_ENABLED=true`).
- **Teto mensal:** padrão 5000 centavos (US$ 50), editável por API, `PUT /api/v1/sla/platform-params/ai_monthly_budget_cents` com `{"value": <centavos>}` (platform_admin); ainda sem tela.
- **Antes de promover:** conferir que os tenants do SOC batem com os clientes — `SELECT DISTINCT internal_customer_id FROM n_infraops_tenant_mappings WHERE external_platform='wazuh'` contra `n_infraops_customers.key` — e que `NINF_AI_BUDGET_ALERT_EMAIL`, `NINF_TRANSACTIONAL_EMAIL_ENABLED` e a chave do Resend estão definidos.
- **Migração:** aditiva (`python -m app.migrate`): tabela `n_ai_decisions` e coluna `ai_external_allowed` no cliente.
- **Rollback:** imagem anterior; tabela e coluna podem ficar.
