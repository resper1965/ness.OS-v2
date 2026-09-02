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
