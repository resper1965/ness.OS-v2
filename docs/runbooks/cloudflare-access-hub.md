# Cloudflare Access + Hub — Configuração

## Objetivo

Autenticar usuários do Hub via Cloudflare Access (Zero Trust), eliminando
a necessidade de login local. O Access injeta o header `Cf-Access-Jwt-Assertion`
em toda requisição; o Hub valida o JWT e extrai o e-mail.

## Pré-requisitos

- Acesso ao painel Cloudflare Zero Trust (`https://one.dash.cloudflare.com/`)
- Domínio `hub.ness.com.br` com proxy (laranja) ativo no DNS
- `cloudflared` rodando na VPS (ou túnel configurado no Zero Trust)

## Passo 1 — Criar a aplicação Access

1. Acesse **Zero Trust → Access → Applications**
2. Clique **Add an application** → **Self-hosted**
3. Preencha:
   - **Application name**: `ness.OS Hub`
   - **Session duration**: `8h` (ou o que preferir)
   - **Application domain**: `hub.ness.com.br`
   - **Identity providers**: escolha o IdP (Entra ID ou GitHub, conforme configurado)
   - **Protect cookie**: ative `SameSite=Lax` (necessário para requisições cross-origin da API)
4. Clique **Next** e defina as políticas:
   - **Policy name**: `Equipe ness.`
   - **Include**: `Emails ending in` → `@ness.com.br`
   - (adicione políticas para domínios de cliente conforme necessário)
5. Clique **Next**, revise, **Add application**

## Passo 2 — Configurar o túnel (se ainda não existir)

```bash
# Na VPS:
sudo cloudflared tunnel create ness-hub
# Anote o UUID do túnel

# Configurar rota:
sudo cloudflared tunnel route dns ness-hub hub.ness.com.br

# Criar config.yml:
sudo mkdir -p /etc/cloudflared
sudo tee /etc/cloudflared/config.yml <<'EOF'
tunnel: <UUID_DO_TUNEL>
credentials-file: /etc/cloudflared/<UUID_DO_TUNEL>.json

ingress:
  - hostname: hub.ness.com.br
    service: http://localhost:8000
  - service: http_status:404
EOF

# Iniciar como serviço:
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

Se o Hub já expõe porta 443 com Caddy e o DNS já é proxied (laranja),
o túnel é opcional — o Access funciona com DNS proxied direto.
Nesse caso, pule este passo.

## Passo 3 — Pegar o AUD tag

1. Em **Zero Trust → Access → Applications**, clique na aplicação `ness.OS Hub`
2. Na aba **Overview**, copie o **Application Audience (AUD)** tag
   (formato: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
3. Adicione ao `.env` da VPS:

```bash
NINF_CF_ACCESS_ENABLED=true
NINF_CF_ACCESS_AUD=<aud-tag-copiado>
```

## Passo 4 — Testar

```bash
# Sem token → 401
curl -sS -o /dev/null -w '%{http_code}' https://hub.ness.com.br/api/incidents

# Com token (gere um token de serviço em Access → Service Auth)
curl -sS -H "Cf-Access-Jwt-Assertion: $(cf-access-token)" \
  https://hub.ness.com.br/api/incidents
```

## Vinculando usuários Access a usuários locais

O middleware injeta `request.state.cf_email` com o e-mail do token.
Para completar o fluxo:

1. O frontend detecta que não há sessão local → redireciona para `hub.ness.com.br`
2. O Access autentica → navegador recebe o cookie `CF_Authorization`
3. O backend recebe o header `Cf-Access-Jwt-Assertion`, extrai o e-mail
4. Próximo passo (PR futuro): criar sessão local automaticamente
   (`/api/auth/access-login`) que casa `cf_email` com `User.email`

Por enquanto, o backend valida o token e expõe o e-mail no request state.
O restante do fluxo de sessão será implementado em seguida.
