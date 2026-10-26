# Hub/AIOps — release imutável em 2026-10-12

**Janela:** 2026-10-12 08:55–09:12 BRT (11:55–12:12 UTC)  
**Host:** AIOps `144.91.115.242`  
**Commit de release:** `144317fd5262ecf242b118774573a62df8e88d78`  
**Escopo:** API, `worker-alerts`, `worker-ml` e frontend. PostgreSQL, Redis,
GLPI, Authentik, Caddy, n8n e Evolution não foram reiniciados.

## Pré-condições aprovadas

- Backup novo `20261012T085531-0300`: marcador `COMPLETED` e todos os
  SHA-256 do conjunto validados no diretório do conjunto.
- Diretório de release isolado criado em
  `/opt/n-infraops/releases/144317fd5262ecf242b118774573a62df8e88d78/app`;
  o diretório ativo `/opt/n-infraops/app` foi preservado como rollback.
- Manifesto local, com o Compose de produção e tickets explicitamente
  selecionados, retornou `release_ready=true` sem blockers.
- Login temporário no GHCR foi removido depois do push; não há credencial
  `ghcr.io` persistida no host.

## Artefatos publicados e efetivos

| Serviço | Referência imutável |
|---|---|
| API e workers | `ghcr.io/resper1965/ninf-api@sha256:cd3224cfa5a361f5bf24d9f2c02bcfcb5af2e784e8c8dd4d1c3a64b77a1caadf` |
| Frontend | `ghcr.io/resper1965/ninf-frontend@sha256:604e9b9e764f86b1920a68f160298807be7fd405a406bfcbc47d0041c039f425` |

Os dois pacotes foram conferidos como privados no GHCR.

## Ensaio, migração e promoção

1. O build padrão falhou antes de criar artefato porque a interface `docker0`
   do host não existe, embora as redes Compose existentes estejam saudáveis.
   BuildKit com `--network host` construiu os artefatos sem reiniciar Docker ou
   alterar a rede dos serviços.
2. O canário da API, em container separado na rede `app_ninf-net`, revelou a
   ausência da tabela `n_infraops_incident_actions`. A migração versionada
   `app/migrate.py` foi executada uma vez; é aditiva/idempotente e confirmou a
   tabela. O canário então aprovou `GET /ready` e foi removido.
3. A promoção recriou somente os quatro serviços do escopo. API e workers
   ficaram `healthy`; o frontend respondeu HTTP 200 e o Caddy alcançou o
   frontend pela rede interna.
4. O rollback controlado recriou os quatro serviços com as imagens locais
   anteriores (`app-api`, `app-worker-alerts`, `app-worker-ml` e
   `app-frontend`), todos com healthcheck Docker aprovado. A versão anterior
   não expõe `/ready`; sua rota antiga `/webhook/health` exige autenticação e
   respondeu 401, por isso não é usada como sonda anônima.
5. A release imutável foi reaplicada e passou as mesmas sondas finais.

## Resultado final observado

- `ninf-api`: `running`, `healthy`, `GET /ready` retorna `{"status":"ready"}`.
- `ninf-worker-alerts`: `running`, `healthy`.
- `ninf-worker-ml`: `running`, `healthy`.
- `ninf-frontend`: `running`, resposta HTTP 200 local.
- Timer `ness-aiops-backup.timer`: `active`, próxima execução às 23:00 BRT.

## Limites e acompanhamento

- A interface `docker0` ausente permanece um defeito de plataforma: os builds
  devem continuar usando rede `host` até uma manutenção específica do Docker,
  com teste e rollback próprios. Não reiniciar Docker durante a observação.
- A migração é aditiva, mas o rollback de aplicação não desfaz schema; esse
  comportamento foi aceito para este ensaio porque a versão anterior continuou
  saudável após a adição.
- A workflow de publicação foi aberta como PR #65, mas a política do repositório
  exige revisão e quatro checks para mescla em `main`. A publicação desta
  release foi feita diretamente no host com token em stdin, removido ao final.
- G0 continua **parcial** até CI completo em runner limpo, promoção do workflow
  revisado e observação operacional; esta evidência fecha a lacuna de digest,
  canário e rollback para o Hub.
