# Isolamento Hub ↔ GLPI — achados e proposta (Task 2.3, Steps 3 e 4) — 03/11/2026

Só leitura (`docker inspect`, nomes de variáveis; nenhum valor foi lido ou impresso).

## Achados

1. **Senha root do MariaDB do GLPI no ambiente do Hub.** `ninf-api`, `ninf-worker-alerts` e `ninf-worker-ml` têm `NINF_GLPI_DB_ROOT_PASSWORD` e `NINF_GLPI_DB_PASSWORD`. Causa: `env_file: .env` em `app/docker-compose.yml` (linhas 14, 46, 76) passa o arquivo inteiro. Nenhum `.py` do backend lê essas duas variáveis; só `docker-compose.tickets.yml` (serviços `glpi-db` e `glpi`) as usa, por interpolação.
2. **Mesma rede.** Hub e `ninf-glpi-db` estão em `app_ninf-net`; o banco não publica porta no host. Hub comprometido → conexão direta ao banco como root, sem passar pelo gateway nem pelo App-Token.
3. **Risco do ADR 0020 (aceito em 28/10) continua:** App-Token do Hub + `user_token` da 106 abre sessão a partir do Hub. O `NINF_GLPI_USER_TOKEN` do Hub é outro (conta do Hub), mas o achado 1 torna o 0020 secundário: quem lê o ambiente do Hub já tem mais do que a 106 daria.
4. Contêineres sem a variável: `ninf-glpi`, gateway, `caddy`, `n8n`, `authentik-*`, `postgres`, `redis`, `evolution`, `psono`.

## Proposta (recomendo A)

**A. Tirar as duas variáveis do ambiente do Hub e separar redes.**
- Mover `NINF_GLPI_DB_ROOT_PASSWORD` e `NINF_GLPI_DB_PASSWORD` do `app/.env` para `/etc/ness-os/glpi-db.env` (root 0600), lido só pelos serviços `glpi-db` e `glpi`.
- **Contrato a mudar junto** (senão a implantação quebra ou a senha volta ao Hub):
  1. `app/docker-compose.tickets.yml` (linhas 7–30) interpola `${NINF_GLPI_DB_*:?}`. `env_file` de serviço não alimenta interpolação: trocar por `env_file: /etc/ness-os/glpi-db.env` nos dois serviços, com `MYSQL_ROOT_PASSWORD`/`MYSQL_PASSWORD`/`DB_PASSWORD` nomeados no arquivo, ou subir o compose com `--env-file`.
  2. `infra/scripts/aiops-runtime-preflight.sh` (linhas 48–89) deriva as exigências e só confere o `--env-file` (padrão `app/.env`): passar a checar também `glpi-db.env`.
  3. `infra/scripts/glpi-pin-and-rotate.sh` (linhas 89–93) tem `/opt/n-infraops/app/.env` fixo e anexa as duas credenciais ali: mudar para gravar em `glpi-db.env`. **Rodar o rotator antes disso devolveria a senha root ao `.env` do Hub.**
- Rede `glpi-db-net` interna, só com `glpi-db` e `glpi` (e o necessário ao backup). O Hub fica em `ninf-net` e fala com o GLPI pela API.
- Rotacionar as duas senhas depois, porque estiveram no ambiente do Hub, com o rotator já corrigido.
- Rollback: recolocar as variáveis no `.env`, rede anterior e compose anterior; recriação dos contêineres do GLPI (~1–2 min, fora do backup das 23:00 -03).
- Custo: mudança em produção no compose, no `.env`, nos dois scripts e no banco. **Pede OK do Ricardo e janela curta; não aplicado.** Os três ajustes de código/script entram em PR com teste antes de mexer em produção.

**B. Só rede (sem mexer no `.env`).** Não resolve o achado 1: a senha continua no ambiente do Hub.

**C. Manter como está.** Risco: root no banco do GLPI a partir do Hub. Não recomendo.

## Verificação (Step 4)

Só vale **depois de recriar** `ninf-api`, `ninf-worker-alerts` e `ninf-worker-ml` com o `.env` novo (inspecionar contêiner antigo não prova nada): `docker inspect` sem as duas variáveis; `grep -c GLPI_DB app/.env` = 0 também **depois** da rotação; `getent hosts glpi-db` a partir do `ninf-api` sem resolver; preflight de release passa; GLPI responde (`/apirest.php` interno 200, UI 302 para o SSO); `cmdb_sync` dry-run funciona; gateway de manutenção segue lendo o ID 14.
