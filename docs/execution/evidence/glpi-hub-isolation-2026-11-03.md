# Isolamento Hub ↔ GLPI — achados e proposta (Task 2.3, Steps 3 e 4) — 03/11/2026

Só leitura (`docker inspect`, nomes de variáveis; nenhum valor foi lido ou impresso).

## Achados

1. **Senha root do MariaDB do GLPI no ambiente do Hub.** `ninf-api`, `ninf-worker-alerts` e `ninf-worker-ml` têm `NINF_GLPI_DB_ROOT_PASSWORD` e `NINF_GLPI_DB_PASSWORD`. Causa: `env_file: .env` em `app/docker-compose.yml` (linhas 14, 46, 76) passa o arquivo inteiro. Nenhum `.py` do backend lê essas duas variáveis; só `docker-compose.tickets.yml` (serviços `glpi-db` e `glpi`) as usa, por interpolação.
2. **Mesma rede.** Hub e `ninf-glpi-db` estão em `app_ninf-net`; o banco não publica porta no host. Hub comprometido → conexão direta ao banco como root, sem passar pelo gateway nem pelo App-Token.
3. **Risco do ADR 0020 (aceito em 28/10) continua:** App-Token do Hub + `user_token` da 106 abre sessão a partir do Hub. O `NINF_GLPI_USER_TOKEN` do Hub é outro (conta do Hub), mas o achado 1 torna o 0020 secundário: quem lê o ambiente do Hub já tem mais do que a 106 daria.
4. Contêineres sem a variável: `ninf-glpi`, gateway, `caddy`, `n8n`, `authentik-*`, `postgres`, `redis`, `evolution`, `psono`.

## Proposta (recomendo A)

**A. Tirar as duas variáveis do ambiente do Hub e separar redes.**
- Mover `NINF_GLPI_DB_ROOT_PASSWORD` e `NINF_GLPI_DB_PASSWORD` do `app/.env` para um arquivo só do GLPI (por exemplo `/etc/ness-os/glpi-db.env`, root 0600), usado por `docker-compose.tickets.yml` via `env_file` nos serviços `glpi-db` e `glpi`. O `.env` do Hub deixa de tê-las.
- Rede `glpi-db-net` interna, só com `glpi-db` e `glpi` (e o que precisar do banco, como o backup). O Hub continua em `ninf-net` falando com o GLPI pela API.
- **Rotacionar as duas senhas** depois, porque estiveram no ambiente do Hub (`infra/scripts/glpi-pin-and-rotate.sh` já faz isso).
- Rollback: recolocar as variáveis no `.env` e a rede anterior; recriação dos contêineres do GLPI (indisponibilidade de ~1–2 min, fora do backup das 23:00 -03).
- Custo: mudança em produção no compose, no `.env` e no banco do GLPI. **Pede OK do Ricardo e janela curta; não aplicado.**

**B. Só rede (sem mexer no `.env`).** Não resolve o achado 1: a senha continua no ambiente do Hub.

**C. Manter como está.** Risco: root no banco do GLPI a partir do Hub. Não recomendo.

## Verificação (Step 4)

Depois de A: `docker inspect` dos três contêineres do Hub sem as duas variáveis; `getent hosts glpi-db` a partir do `ninf-api` sem resolver; GLPI responde (`/apirest.php` interno 200, UI 302 para o SSO); `cmdb_sync` dry-run funciona; gateway de manutenção segue lendo o ID 14.
