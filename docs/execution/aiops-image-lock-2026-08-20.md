# Lock de imagens AIOps — 20/08/2026

Este arquivo registra os digests observados nos contêineres em execução. O Compose local foi atualizado para referenciar exatamente esses artefatos, sem `pull`, recriação ou alteração da produção.

| Serviço | Referência observada | Digest fixado |
|---|---|---|
| GLPI | `elestio/glpi:latest` | `sha256:48ec3ce559fda9eaf73c6fe2f0fc2dd382ef013f2dda14004f34ee88ec17c8b8` |
| MariaDB GLPI | `mariadb:10.11` | `sha256:be981e4113326ada8d6004174dd09eeaefc03094037f811182a52d4f2e737350` |
| Caddy | `caddy:2-alpine` | `sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648` |
| Evolution API | `evoapicloud/evolution-api:latest` | `sha256:966625532d9076a2381e973a271307d107e6f070450de3abeeea8bd18be07252` |
| Evolution Manager | `evoapicloud/evolution-manager:latest` | `sha256:cbfeb314afb9d380068c86151fbfa9fd7905d0ad74da77fad01f2c85d01a025a` |
| n8n | `docker.n8n.io/n8nio/n8n:latest` | `sha256:4b0b4a48faeaa5e17ea57a578a53078fb6c9b8eb65d1573eb68d8ce8f6022da0` |
| Authentik | `ghcr.io/goauthentik/server:2026.5.6` | `sha256:ed120caf710ccf82ef0026f0bc74e51615bc95ebff228a7a2d6fc60c441c3868` |
| TimescaleDB | `timescale/timescaledb:latest-pg16` | `sha256:ba149561ad4ddff5940d6eb0a0df60aefd1355cee1a450928f271267038fc888` |
| Redis | `redis:7-alpine` | `sha256:6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` |

## Observações

- O hash do Compose local não coincide com o arquivo atualmente existente na VPS, pois o repositório contém mudanças ainda não promovidas. O lock não deve ser copiado isoladamente para produção.
- Antes do próximo deploy, comparar o Compose remoto e o local sem transportar segredos, validar `docker compose config`, criar backup e ensaiar rollback.
- Os digests preservam temporariamente o estado atual, inclusive componentes em processo de substituição por licença. Fixar não significa aprovar a permanência.
- Imagens próprias (`app-api`, `app-frontend` e workers) ainda precisam de tag imutável associada ao commit, digest de registry, proveniência e SBOM.
