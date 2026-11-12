# Fase B — ligar o login Entra ID no Hub (só operadores ness.)

OK do Ricardo em 06/11/2026. Escopo: login OIDC do Hub pelo Entra. GLPI, n8n e Zabbix continuam no Authentik (Fase C/D). Clientes convidados ficam fora até restringir a colaboração externa.

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
