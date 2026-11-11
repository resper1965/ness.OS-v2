# Hub — SSO do Authentik desligado (11/11/2026)

## Por quê

O botão de SSO do Hub levava ao Authentik (`sso.ness.com.br`), que oferece login pelo Google.
O ADR 0015, aceito em 05/11, define o Entra ID como único IdP e manda o Authentik sair. Além do
desvio do ADR, o caminho era uma armadilha: em 11/11 o navegador do Ricardo tinha sessão de outro
usuário no Authentik (`myoshida`), e o SSO reautenticava como essa pessoa. O login por e-mail e senha
do Hub sempre funcionou e é o que está em uso real.

## O que foi feito

Autorização: "pode desligar", em 11/11, sobre a proposta de `OIDC_ENABLED=false` com backup e
recriação de `api`.

- `NINF_OIDC_ENABLED=true` → `false` no `.env` da release `4a72949` e no canônico `/opt/n-infraops/app/.env`.
- Backup dos dois antes: `/opt/n-infraops/change-backups/oidc-off-20261111T101459/{release,app}.env`.
- `docker compose config -q` OK; recriado só o `ninf-api`. Workers não leem essa configuração.
- Rollback: restaurar os dois `.env` do backup e recriar o `api`.

## Verificação

- `GET /api/auth/oidc/config` → `"enabled": false` (HTTP 200).
- `ninf-api` `healthy` após a recriação; `/ready` = 200 no contêiner.
- `worker-alerts` e `worker-ml` não foram tocados (`healthy`, sem recriação).

## Achados

- **A senha do `resper@ness.com.br` guardada em `projetos.env` está desatualizada.** A conta (id 3,
  `admin`, ativa) tem hash e registra `last_login` em 10/11 18:27, mas o login com o valor do arquivo
  devolve 401. O valor real só existe no banco; a cópia do arquivo precisa ser atualizada ou a senha,
  redefinida. Não alterei nada.
- **O botão de SSO continua visível** na tela de login e agora responde "Login por SSO desativado no
  servidor". Esconder o botão quando `enabled=false` fica para o próximo lote de frontend.
- **Sessão do `akadmin` no Zabbix de destino** aberta desde 10/11 11:32 (teste de login). Não foi
  encerrada; o `akadmin` segue como Super admin e com nome "authentik", herança do restore.
