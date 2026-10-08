# Hub/GLPI — deduplicação e retry — 08/09/2026

## Escopo entregue localmente

Continuação da onda F4 do plano funcional. A implementação de busca e
reutilização de tickets por marcador já estava no worktree. Esta etapa corrige
o controle de concorrência do worker e a propagação das falhas do GLPI.

- A aquisição de `ninf:inhibit:{fingerprint}` usa `SET NX EX`, com token único
  por tentativa e o TTL existente de 300 segundos. Uma tentativa que perde a
  disputa não executa o pipeline.
- Em caso de erro, a liberação compara o token e remove a chave atomicamente
  por Lua. Uma tentativa antiga não remove a chave de um proprietário novo.
- Falha na aquisição pelo Redis chega ao retry do Celery sem executar o fluxo.
- Falha no GLPI permite persistir o incidente local e somente depois propaga
  o erro ao retry existente: até três retries, com intervalo configurado de
  cinco segundos. A sessão GLPI continua sendo encerrada no `finally`.
- Tentativas com falha no GLPI não disparam WhatsApp nem Web Push. O retorno
  `whatsapp_sent` passa a refletir a conclusão da chamada de envio, em vez de
  inferir envio pela urgência; não representa confirmação de entrega.
- Uma falha de comentário após a criação do ticket pode ser retomada pela
  busca do marcador, reutilizando o ticket sem uma segunda criação.

## Evidência

Os testes novos reproduziram o processamento após perder a disputa pela chave,
a liberação sem identificação do proprietário e a falha do GLPI que não
chegava ao retry. Após a correção:

```text
python -m pytest -q
162 passed in 3.25s

ruff check app/workers/alerts.py tests/test_alert_glpi_idempotency.py
All checks passed!

python -m black --check app/workers/alerts.py tests/test_alert_glpi_idempotency.py
2 files would be left unchanged.
```

Execução em WSL/Ubuntu, Python 3.12, ambiente temporário
`/tmp/ness-hub-glpi-venv` com acesso aos pacotes locais; Redis Python 5.3.1.
Os testes usam substitutos das integrações e da sessão de banco: não comprovam
um commit em PostgreSQL real ou uma transação remota no GLPI.

Uma prova adicional com `fakeredis` e execução Lua verificou os dois resultados:
liberar a própria chave e preservar uma chave substituída por outro worker.
Não foi necessário alterar as dependências do projeto.

## Limites e próximo gate

Esta evidência é local e não promove F4. Não houve deploy, criação de ticket
real, envio de mensagens ou alteração dos gates de canais.

A exclusão entre workers vale durante o TTL de 300 segundos. Ainda é necessário
provar o comportamento de tarefas que excedam esse prazo ou percam o processo
antes da liberação; esta etapa não oferece garantia global de execução única.
A reutilização de um ticket após falha no comentário não reenvia o comentário.

O próximo gate é o incidente sintético em ambiente integrado, com canais reais
desligados: Zabbix → incidente local → GLPI → atualização do hub → encerramento,
incluindo isolamento de tenant, resposta perdida após criação, retry e auditoria.
Também permanecem pendentes a contagem de ocorrências frente a reentregas e a
deduplicação de notificações diante de falhas posteriores ao envio.

## Reversão

Reverter somente as mudanças desta etapa em `app/workers/alerts.py` e os testes
correspondentes, preservando a implementação de marcador e as demais alterações
anteriores do worktree. Não há migration nem alteração de schema. As chaves de
inibição expiram pelo TTL existente.
