# F1 da IA nos chamados — aviso à operação

**Conclusão:** a partir da promoção, o Web Push de alerta sai só pela severidade do Zabbix (≥ 4, HIGH/CRITICAL). A IA não escala mais. Divergências aparecem na tela "IA".

Status: **não promovida**. Enviar este aviso antes; promoção com OK do Ricardo.

## O que muda para quem atende

- **Push:** só dispara quando a severidade de origem no Zabbix é ≥ 4. Antes, a IA podia subir a urgência e disparar push.
- **IA não escala:** ela deixa de subir urgência, e `isolation_required` não gera mais push.
- **Rótulo de severidade** no Web Push e no Loki passa a vir da origem, não da IA.
- **Tela "IA"** (`?view=ai`): métricas, retorno "útil" do analista e divergências (motor × modelo no SOC).
- **Cliente:** o formulário de edição ganhou a caixa "IA externa permitida" (desmarcar = o cliente não vai ao modelo externo).

## Para quem opera o Hub

- **Variável nova:** `NINF_AI_BUDGET_ALERT_EMAIL` (e-mail que recebe o alerta do teto mensal; um por mês). O alerta só sai com e-mail transacional ligado (`NINF_TRANSACTIONAL_EMAIL_ENABLED=true`).
- **Teto mensal:** padrão 5000 centavos (US$ 50), editável nos parâmetros da plataforma.
- **Migração:** aditiva (`python -m app.migrate`): tabela `n_ai_decisions` e coluna `ai_external_allowed` no cliente.
- **Rollback:** imagem anterior; tabela e coluna podem ficar.
