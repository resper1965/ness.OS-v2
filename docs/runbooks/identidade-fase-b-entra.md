# Fase B — ligar o login Entra ID no Hub (só operadores ness.)

OK do Ricardo em 06/11/2026. Escopo: login OIDC do Hub pelo Entra. O GLPI já saiu do Authentik (seção GLPI, abaixo); o Zabbix antigo continua nele até o D+2 do cutover. Clientes convidados ficam fora até restringir a colaboração externa.

## 1. Entra (portal, admin do tenant)
1. Conferir **Propriedades → Gerenciar padrões de segurança = Habilitado** (MFA). Se estiver desligado, parar e avisar o Ricardo.
2. **Registros de aplicativo → Novo**: nome `ness.OS Hub`, contas **somente deste diretório**, redirecionamento **Web** `https://hub.ness.com.br/callback`.
3. **Certificados e segredos → Novo segredo**, validade 24 meses. Guardar no Psono (`Hub OIDC Entra`) e anotar a data de expiração. Não colar em chat nem log.
4. **Configuração de token → Adicionar declaração opcional (ID)**: `email`.
4a. **Autenticação → URLs de logout / redirecionamento:** incluir `https://hub.ness.com.br` (usado no `post_logout_redirect_uri`).
5. Anotar o **ID do aplicativo (cliente)** e o **ID do diretório (tenant)**.

## 2. Hub (`/opt/n-infraops/app/.env` e o `.env` da release ativa; backup antes)
```
NINF_OIDC_ENABLED=true
NINF_OIDC_CLIENT_ID=<id do aplicativo>
NINF_OIDC_CLIENT_SECRET=<do Psono>
NINF_OIDC_ISSUER=https://login.microsoftonline.com/<tenant>/v2.0
NINF_OIDC_JWKS_URL=https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys
NINF_OIDC_TOKEN_URL=https://login.microsoftonline.com/<tenant>/oauth2/v2.0/token
NINF_OIDC_AUTHORIZE_URL=https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize
NINF_OIDC_LOGOUT_URL=https://login.microsoftonline.com/<tenant>/oauth2/v2.0/logout
NINF_OIDC_SCOPE=openid profile email
```
Recriar só a `api` (`up -d --no-deps --force-recreate api`). Exige a release com `GET /api/auth/oidc/config` (sem ela o botão ainda vai para o Authentik).

## 3. Vínculos (por operador)
Seguir [identidade-fase-a.md](identidade-fase-a.md): a pessoa clica em **Entrar com SSO**, recebe 403, o log da API mostra `OIDC sem vínculo: iss='…' sub='…'` (com o Entra, o `sub` do log é o `oid`; token do Entra sem `oid` é recusado); o `platform_admin` cadastra com `POST /api/auth/identities`. Comece pelo Ricardo.

## 4. Verificar
- `GET /api/auth/oidc/config` mostra `enabled=true` e as URLs do Entra, sem segredo.
- Operador vinculado entra pelo Entra com MFA; não vinculado recebe 403; **login local por senha continua funcionando**.

## Rollback
`NINF_OIDC_ENABLED=false` (ou restaurar o `.env` do backup) e recriar a `api`. O login local não depende do OIDC.

# GLPI (`n-ticket`) pelo Entra — aplicado em 12/11/2026

Mesmo padrão do `zabbix-web`: Cloudflare Access com o IdP Entra na frente, sem app registration próprio.

- **Fluxo:** DNS `n-ticket` (CNAME proxied) → túnel `aiops-glpi` (`d3d49aa6-…`, container `ninf-cloudflared-glpi`, token em `/etc/ness-os/cloudflared-glpi.env`) → `http://ninf-glpi:80`. O túnel valida o JWT do Access (`access.required`, aud do app). O bloco `n-ticket` saiu do Caddyfile; a origem não fica exposta.
- **Access:** app `n-ticket (GLPI)` (`263745ab-…`), sessão 8h, só IdP Entra, política `email_domain = ness.com.br`. `apirest.php` e paths com `%xx` respondem 403 no túnel.
- **GLPI:** variável SSO `HTTP_CF_ACCESS_AUTHENTICATED_USER_EMAIL`, `existing_auth_server_field_clean_domain=1` (login = parte antes do `@`), `is_users_auto_add=0` (e-mail sem usuário cadastrado é recusado), logout `https://n-ticket.ness.com.br/cdn-cgi/access/logout`.
- **Usuários:** o login GLPI precisa ser igual à parte local do e-mail `@ness.com.br`. Usuário novo: criar no GLPI com esse login antes do primeiro acesso.
- **Verificar:** sem sessão, `https://n-ticket.ness.com.br/` → 302 para `ness.cloudflareaccess.com`; pela rede interna, `Cf-Access-Authenticated-User-Email: <login>@ness.com.br` em `/front/login.php` → `central.php`; e-mail sem cadastro → 400.
- **Quebra de vidro:** pela rede interna (`docker run --network app_ninf-net curlimages/curl …`) com o cabeçalho de um Super-Admin. Qualquer container na `ninf-net` consegue fazer isso — o mesmo risco que existia com o `X-Remote-User`.
- **Rollback:** backup em `/opt/n-infraops/change-backups/glpi-entra-*`. Restaurar `Caddyfile`, `docker-compose.tickets.yml`, `glpi-sso-config.tsv` (`ssovariables_id=8`, `clean_domain=0`, `is_users_auto_add=1`, logout `https://sso.ness.com.br`), recriar `caddy`, parar `cloudflared-glpi` e voltar o DNS para `A 144.91.115.242` sem proxy.
