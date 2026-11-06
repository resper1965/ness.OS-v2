# Saída do Authentik antecipada — plano

> **Para quem executa:** passos com `- [ ]`. Passo marcado **[FRASE]** só roda com a frase explícita do Ricardo dizendo o efeito (ex.: "pode tirar o forward_auth do n8n agora"). Um sistema por vez; o próximo só começa com o anterior verificado.

**Objetivo:** o Entra ID vira o único login de pessoas; o Authentik é desligado sem deixar nenhuma tela exposta sem porteiro e sem trancar ninguém para fora.

**Decisão:** [ADR 0015](../../adr/0015-entra-id-identity-local-authorization.md), antecipação aprovada pelo Ricardo em 06/11/2026. Custo zero: Entra Free (*security defaults*), Cloudflare Zero Trust Free (≤ 50 usuários).

## Fatos (leitura de 06/11)

| Sistema | Hoje | Alvo |
|---|---|---|
| Hub `hub.ness.com.br` | Login local; OIDC desligado (aponta para o Authentik) | OIDC Entra direto no app (PR `feat/hub-oidc-entra`), login local de reserva |
| Zabbix | SAML do Authentik | Access (Entra) na frente + login local do Zabbix; segue o [plano de cutover](2026-11-06-zabbix-cutover-acesso-cloudflare.md) |
| n8n `n8n.ness.com.br` | `forward_auth` Authentik + login do próprio n8n | Access (Entra) na frente + login do n8n |
| GLPI `n-ticket.ness.com.br` | `forward_auth` Authentik **e** login por `REMOTE_USER` (35 contas `authtype` 3, nenhuma usada até 29/10) | Access (Entra) na frente + login local do GLPI por pessoa |
| `api.ness.com.br`, `waba`, `cofre` | basicauth / app próprio / Psono nativo | Sem mudança |

O Caddy de produção é `app/Caddyfile`. Hoje, sem túnel, as 80/443 da VPS AIOps estão abertas: o Access só protege se a origem aceitar **apenas** o túnel (ou IPs da Cloudflare com validação do JWT do Access).

## Restrições
- Nunca deixar uma tela sem porteiro: o `forward_auth` só sai depois que o Access daquele host respondeu 302 para o login do Entra num teste anônimo.
- Emergência: os *security defaults* não permitem excluir conta do MFA, então a reserva não é conta do Entra: é o login local de cada sistema + SSH com chave. Testar antes do passo 6.
- Clientes não entram em Zabbix, GLPI, n8n nem Psono (ADR 0015, ponto 5).
- Segredos (client secret do Entra, token do túnel, service tokens do Access) vão para o Psono; nunca em chat, log ou Git.

## Passos

### 1. Hub pelo Entra — **[FRASE]** (já dada em 06/11: "ligue")
- [ ] Merge do PR `feat/hub-oidc-entra` e promoção (API + frontend).
- [ ] Seguir `docs/runbooks/identidade-fase-b-entra.md`; vínculo do Ricardo primeiro.
- [ ] Verificar: login Entra com MFA ok, não vinculado = 403, login local ok.

### 2. Túnel na VPS AIOps — **[FRASE]**
- [ ] Conferir `sha256` de `/opt/n-infraops/app/Caddyfile` contra `app/Caddyfile` da `main`; divergiu, reconciliar antes.
- [ ] Instalar `cloudflared` (serviço systemd, só saída), túnel `aiops`, token no Psono.
- [ ] Rotas novas **sem trocar DNS ainda**: hostnames de teste `n8n-t.ness.com.br` e `n-ticket-t.ness.com.br` → `https://127.0.0.1:443` com `originServerName` do host real.
- [ ] Cloudflare Zero Trust: login method **Microsoft Entra ID** (app de registro próprio, segredo no Psono); policy `ness-tecnicos` = e-mails/grupo de operadores ness.
- Rollback: parar o `cloudflared`; nada em produção mudou.

### 3. n8n — **[FRASE]**
- [ ] Application do Access em `n8n.ness.com.br`; trocar o DNS para o túnel (proxied).
- [ ] Teste anônimo: 302 para o Entra. Operador: Entra → tela de login do n8n → entra.
- [ ] Webhooks públicos do n8n (`/webhook/*`), se usados pelo Hub/Zabbix: **bypass** no Access só para esse caminho, ou service token; conferir no log que continuam chegando.
- [ ] Só então tirar o `forward_auth` do bloco `n8n.ness.com.br` no `app/Caddyfile` (PR + deploy do arquivo + `caddy reload`).
- Rollback: DNS de volta para o IP (proxied=false) e Caddyfile anterior.

### 4. GLPI — **[FRASE]**
- [ ] Antes: decidir as contas. Recomendado: ativar login local (`authtype` 1) para os técnicos que usam a tela, senha forte no Psono pessoal, e desativar as 36 contas locais nunca usadas que duplicam as SSO (lista em `docs/execution/evidence/credenciais-82-2026-10-29.md`).
- [ ] Application do Access em `n-ticket.ness.com.br`; o Hub usa a API do GLPI pelo gateway interno — conferir que **não** passa por esse hostname; se passar, service token.
- [ ] Trocar DNS para o túnel; teste anônimo 302; técnico entra (Entra → login GLPI).
- [ ] Tirar do Caddy o `forward_auth` e as duas linhas `request_header … Remote-User`; manter o `respond @glpi_api 403`.
- [ ] No GLPI: desligar a autenticação por variável de servidor (`REMOTE_USER`); conferir que cabeçalho forjado não loga.
- Rollback: Caddyfile anterior + reativar a variável de servidor + DNS de volta.

### 5. Zabbix
- [ ] Segue o plano de cutover (Tasks 4 e 6 já pedem **[FRASE]**). Desligar o SAML do Authentik no Zabbix só depois do Access ativo e do login local testado.

### 6. Fechar a origem — **[FRASE]**
- [ ] Testar emergência: com o túnel parado, entrar por SSH com chave e abrir cada sistema pelo login local (`ssh -L`).
- [ ] UFW na AIOps: 80/443 só para os ranges da Cloudflare (ou fechar, se tudo estiver no túnel). Lembrar que porta publicada pelo Docker fura o UFW: conferir `docker ps` e `iptables -L DOCKER-USER`.

### 7. Desligar o Authentik — **[FRASE]**
- [ ] 7 dias sem login no Authentik (log) e sem incidente de acesso.
- [ ] Backup do banco e da mídia do Authentik guardado 30 dias.
- [ ] Parar os contêineres; remover do compose, o bloco `sso.ness.com.br` do Caddy, o DNS e os segredos; atualizar `infra/docs/as-built-vps.md` e `docs/architecture/ness-os-official-architecture.md`.
- Rollback (até 30 dias): subir os contêineres do backup e restaurar o bloco do Caddy.

## Pronto quando
Nenhuma referência ativa a `authentik` no `app/Caddyfile` e no compose; os quatro sistemas entram pelo Entra; login local testado em todos; Authentik parado com backup.
