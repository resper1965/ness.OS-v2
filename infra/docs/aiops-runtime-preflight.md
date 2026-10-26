# AIOps runtime preflight

Antes de subir a stack, execute na raiz do repositório:

```bash
bash infra/scripts/aiops-runtime-preflight.sh
```

Por padrão, o comando valida `app/.env`, `app/docker-compose.yml` e
`app/docker-compose.tickets.yml`. Para conferir um arquivo candidato sem
substituir `app/.env`, use `--env-file CAMINHO`.

O preflight usa o próprio Compose como fonte de verdade para verificar a presença
não vazia das variáveis marcadas como obrigatórias e a coerência do modelo
mesclado via `docker compose config`. Ele não mostra valores, não acessa produção
e não cria, inicia ou altera containers.

Prova automatizada local:

```bash
bash infra/tests/test-aiops-runtime-preflight.sh
```

## Runner de readiness somente leitura

Valide localmente o preflight e a sintaxe dos dois probes, sem contato de rede:

```bash
bash infra/scripts/aiops-runtime-readiness.sh --env-file /caminho/para/env-candidato
```

Para a execução real, somente no host AIOps e com o ambiente injetado, são
necessários dois opt-ins explícitos:

```bash
set +x
AIOPS_READONLY_EXECUTE=1 bash infra/scripts/aiops-runtime-readiness.sh \
  --env-file app/.env --execute-read-only
```

O runner executa o preflight e, apenas no segundo modo, chama no container `api`
já em execução os CLIs `app.integrations.zabbix_readiness` e
`app.integrations.glpi_readiness`. Ele não inicia containers, aceita somente a
saída esperada com `writes=0` e suprime detalhes de falha para não expor
credenciais. Qualquer etapa ausente, saída inesperada ou probe com erro resulta
em falha fechada.

Teste mockado local:

```bash
bash infra/tests/test-aiops-runtime-readiness.sh
```
