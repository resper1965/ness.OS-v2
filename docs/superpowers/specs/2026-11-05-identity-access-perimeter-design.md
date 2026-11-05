# Identity, Access and Perimeter Design — ness.OS

- **Status:** proposta
- **Data:** 2026-11-05
- **Autor:** Ricardo Esper / agente
- **Base:** ADR 0007 (Authentik como identidade central)

## 1. Intent

Redesenhar identidade, acesso e perímetro do ness.OS para:

1. Substituir o Google OAuth (obsoleto pela migração Google Workspace → M365).
2. Reduzir superfície de ataque (eliminar porta 443 pública).
3. Adicionar MFA universal sem custo adicional.
4. Preservar a capacidade de federar múltiplos IdPs de clientes (multi-tenant).

## 2. Contexto

### Modelo de negócio

O ness.OS é uma plataforma multi-tenant de operação gerenciada, cobrada por UAM (Unidade de Ativo Monitorado). Cada cliente é um tenant isolado. O PricingModule (`app/frontend/src/components/PricingModule.tsx`) define ativos monitorados: endpoints, servidores, firewalls, switches, APs, workloads cloud, apps críticas, tenants M365 e identidades.

### Populações que autenticam

| População | Quem | Tamanho | Necessidade |
|---|---|---|---|
| Operadores internos | Ricardo, Ismael, Rogério, Agnaldo (+ futuros) | ~4–10 | SSO, MFA, roles, break-glass |
| Usuários de cliente | Técnicos e aprovadores do tenant | 0 hoje, cresce | SSO, isolamento por tenant |

### Estado atual

- **IdP:** Authentik (ADR 0007), com Google OAuth como provedor externo para `@ness.com.br`.
- **Perímetro:** porta 443 aberta na VPS, Caddy exposto à internet, proxy Cloudflare desligado (`proxied: false`).
- **DNS:** zona `ness.com.br` no Cloudflare, script de cutover (`infra/scripts/cloudflare-zabbix-dns-cutover.sh`).
- **MFA:** via Authentik — cobre todos os usuários. Google OAuth em modo testing.
- **Migração:** ness. trocou Google Workspace pelo Microsoft 365. Login Google vai parar de funcionar.

## 3. Goals

1. Trocar Google OAuth → Entra ID OIDC como provedor externo para `@ness.com.br`.
2. Adicionar Cloudflare Access + Túnel como borda de autenticação ZTNA.
3. Fechar porta 443 pública da VPS AIOps (Zabbix 10051 permanece; ver 6.1).
4. MFA universal gratuito (Cloudflare Access).
5. Preservar Authentik como hub de federação multi-IdP para clientes.
6. Custo adicional: US$ 0.

## 4. Non-goals

- Substituir Authentik pelo Entra ID como IdP central.
- Adicionar Conditional Access / Intune / Defender (a ness. não tem licença P1/P2).
- Magic WAN — sem malha de sites para conectar.
- Auditar ativos M365 da ness. ou de clientes.
- Remover contas locais break-glass (ADR 0007 obriga).
- Alterar ADR 0007 (Authentik permanece identidade central).

## 5. Anti-goals

- Adicionar custo recorrente (licenças P1, Cloudflare pago).
- Expor porta pública após a migração.
- Depender exclusivamente da Microsoft para recuperação administrativa.

## 6. Design

### Arquitetura

```
                 ┌─────────────────────────────────┐
                 │        Cloudflare Edge           │
                 │  Access (ZTNA) + Gateway + Túnel │
                 └──────────────┬──────────────────┘
                                │ outbound-only (porta 7844)
              VPS (porta 443 FECHADA no firewall)
                                │
                           Caddy local
                           ┌───┼───┐
                      Hub  Zabbix GLPI n8n
                           │
                      ┌────▼────┐
                      │Authentik│  ← hub de federação multi-IdP
                      └────┬────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         Entra ID      Google      SAML do    ...
        (operadores   (cliente A)  cliente B
         @ness.com.br)
```

### Componentes

| Componente | Função | Custo | Plano |
|---|---|---|---|
| **Cloudflare Access** | ZTNA — autentica na borda, exige MFA antes de alcançar a VPS | US$ 0 | Free (≤50 usuários) |
| **Cloudflare Tunnel** (`cloudflared`) | Conecta VPS ao Cloudflare via outbound-only, elimina porta pública | US$ 0 | Binário gratuito |
| **Cloudflare Gateway** | DNS filtering, logging de acesso | US$ 0 | Free |
| **WARP** | Cliente ZTNA nos dispositivos dos operadores | US$ 0 | Cliente gratuito |
| **Authentik** | Hub de federação — aceita OIDC/SAML de qualquer IdP, gerencia grupos, roles e external approval por tenant | US$ 0 | Community |
| **Entra ID Free** | Provedor OIDC externo no Authentik para operadores `@ness.com.br` | US$ 0 | Incluso no M365 |
| **IdP do cliente** | O que o cliente já tiver (Google, Microsoft, SAML) | US$ 0 | Custo do cliente |

### Fluxo de autenticação

```
Operador (navegador ou WARP)
  │
  ▼
https://hub.ness.com.br
  │
  ▼
Cloudflare Access ──► MFA (OTP ou hardware key)
  │ token válido?
  ▼
Túnel cloudflared ──► Caddy ──► Hub
  │
  ▼
Hub redireciona para Authentik
  │
  ▼
Authentik ──► Entra ID (Microsoft login)
  │           │ @ness.com.br → login Microsoft
  │           │ MFA do Entra ID (admin roles)
  │
  ▼
Authentik emite token OIDC → Hub valida → dashboard
```

Two-factor no perímetro (Cloudflare Access) + autenticação no IdP (Entra ID via Authentik). Defesa em profundidade: mesmo se o Entra ID for comprometido, o Access ainda barra.

### External approval (clientes)

Mecanismo existente (`docs/execution/authentik-google-external-approval-2026-09-01.md`) é generalizado: em vez de só Google, o Authentik aceita qualquer provedor OIDC/SAML configurado por tenant. O grupo `SSO-External-Approved` autoriza entrada no Hub; grupos `APP-*` controlam acesso por aplicação.

Documento de external approval será reescrito como genérico (não específico do Google).

### Break-glass

Contas locais no Hub e Zabbix, documentadas, testadas trimestralmente. `akadmin` no Authentik permanece como contingência. Conforme ADR 0007: "Indisponibilidade do SSO não pode impedir recuperação administrativa."

## 6.1 Caminhos que o Access não pode barrar

Access exige sessão de navegador (cookie ou JWT). Tráfego de máquina e chamadas servidor-a-servidor não têm isso e quebram se a política for "todo hostname, MFA". Cada item abaixo precisa de política própria (*bypass* ou *service token*) e teste negativo antes da Fase 3.

| Caminho | Quem chama | Tratamento proposto |
|---|---|---|
| `POST /webhook/zabbix`, `/webhook/glpi`, `GET /webhook/health`, `POST /v1/alerts`, `/api/v1/alerts` | Zabbix, GLPI, n8n (máquina) | *Bypass* restrito a esses **paths** (o Access casa por hostname e path, não por método: o bypass vale para todos os métodos). Os métodos listados são impostos no Caddy (`method` matcher; demais métodos = 405) e o controle de identidade continua sendo o `source-key` da aplicação (`docs/security/access-control-matrix.md`). Teste negativo obrigatório: método fora da lista = 405; sem `source-key` = 401. Opcional: *service token* se a origem suportar cabeçalhos. |
| Token exchange, JWKS e discovery OIDC (Hub → `sso.ness.com.br`) | Backend do Hub | Preferir URL interna (rede Docker) para o issuer server-side. Se o issuer público for obrigatório, *bypass* só para `/application/o/*/token`, `/jwks` e `/.well-known`. |
| `POST /api/auth/oidc/callback` | Navegador | Passa pelo Access normalmente (sessão já existe). Validar que o redirect não cai em laço com o Authentik. |
| `apirest.php` do GLPI (`initSession`) | AIOps (máquina) | Já recebe 302 do Authentik hoje (`gate-0-status.md`). Resolver por rota privada AIOps→GLPI, não por *bypass* público. |
| SSE (stream de incidentes) | Navegador | Confirmar que o Access não encerra conexão longa (TTL de sessão e timeout do túnel). |
| `GET /api/v1/push/config` e service worker da PWA | Navegador/PWA | Confirmar que a PWA instalada no celular (BYOD, ADR 0006) renova a sessão Access sem WARP. |
| Agente/proxy Zabbix → `:10051` (TCP) | Agentes e proxies de clientes | **Fora do túnel HTTP.** A porta 10051 do servidor Zabbix (VPS separada, `144.91.72.202`) continua aberta, restrita por firewall à origem dos agentes. |
| Evolution/WhatsApp (saída) e webhooks de provedores externos | Terceiros | Mapear antes de fechar 443; qualquer entrada de terceiro precisa de *bypass* ou fica fora do escopo. |

Correção ao desenho: "porta 443 fechada" vale para a VPS AIOps (Hub, GLPI, n8n, Authentik). "Zero porta pública" **não** vale para o ecossistema: o Zabbix mantém 10051 por necessidade do protocolo. O Zabbix web (`zabbix.ness.com.br`) só entra no túnel se for movido para a mesma estratégia; hoje está noutra VPS, com o registro A apontando direto para o IP.

## 7. O que não se aplica

| Coisa | Por quê |
|---|---|
| Magic WAN | Sem malha de sites — uma VPS, sem filiais, sem VPCs para interconectar. Reavaliar quando houver múltiplos sites ou clientes com redes OT segregadas que exijam conectividade direta. |
| Magic Transit | Sem prefixos IP próprios para anunciar. DDoS mitigation já coberta pelo plano Free do Cloudflare na borda HTTP. |
| WAF | Caddy + aplicações não têm superfície HTTP pública após o túnel. Reavaliar se serviços forem expostos diretamente no futuro. |
| Intune / Defender / Conditional Access | ness. não tem licenças P1/P2. |

### Ambientes OT

O ness.OS coleta telemetria de ambientes OT via Zabbix agent/proxy — não entra diretamente na rede OT do cliente. O Cloudflare Access + Túnel protege a **plataforma** ness.OS, não a rede OT.

Para clientes com ambientes OT segregados (Purdue model, IEC 62443), a borda Cloudflare é complementar a ferramentas OT-nativas (Claroty, Dragos, Nozomi), que fazem descoberta de ativos, deep packet inspection de Modbus/DNP3/S7 e detecção de anomalia de processo. O ness.OS não substitui essas ferramentas.

Se no futuro um cliente precisar de conectividade direta entre o ness.OS e sua rede OT (ex.: coleta de telemetria via túnel seguro sem VPN), o Magic WAN pode ser reavaliado como conduíte entre zonas IEC 62443. Não está no escopo atual.

## 8. Sequência de migração

```
Fase 0 — Preparação
  1. Criar app registration no Entra ID (OIDC) para o Authentik
  2. Instalar cloudflared na VPS, criar túnel (outbound porta 7844)
  3. Configurar Gateway DNS filtering (modo log, depois enforce)

Fase 1 — Borda (sem derrubar acesso atual)
  4. Criar política Access: permitir @ness.com.br, exigir MFA (OTP). Access é deny-by-default:
     usuários de cliente só entram com uma política de allow própria por tenant (grupo
     Access ou e-mail/domínio do cliente), criada no onboarding do tenant junto com o IdP
     no Authentik. Teste de isolamento: usuário do tenant A não alcança nada do tenant B.
  4a. Criar políticas de bypass/service token da seção 6.1 (webhooks, OIDC server-side)
  5. Apontar túnel para Caddy (localhost)
  6. Testar: WARP → Access → túnel → Caddy → Hub (ainda com Google OAuth)
  7. Validar MFA, logout, sessão, SSE e PWA
  7a. Testes negativos: webhook sem source-key = 401; path fora da lista de bypass sem sessão = bloqueado na borda

Fase 2 — Troca de provedor externo
  8. Adicionar Entra ID OIDC como fonte no Authentik
  9. Migrar enrollment de @ness.com.br: Google → Entra ID
  10. Testar login/logout/roles com conta Microsoft
  11. Remover fonte Google do Authentik
  12. Atualizar external-approval doc (genérico, não Google-específico)

Fase 3 — Fechamento
  12a. Gate: acesso de emergência por SSH + port forward testado (seção 10)
  13. Fechar porta 443 no firewall da VPS AIOps (só cloudflared). Zabbix 10051 permanece.
  14. Remover registro A público do DNS (túnel dispensa)
  15. Atualizar runbook, healthcheck
  16. Manter Authentik, PostgreSQL, backup (Tier 1)
```

## 9. Custos

| Item | Antes | Depois | Delta |
|---|---|---|---|
| Authentik (Docker + PostgreSQL) | US$ 0 | US$ 0 | 0 |
| Cloudflare Access + Túnel + Gateway | — | US$ 0 (Free) | 0 |
| Entra ID | — | US$ 0 (M365) | 0 |
| Google OAuth | US$ 0 | — | 0 |
| **Total** | **US$ 0** | **US$ 0** | **US$ 0** |

## 10. Riscos

| Risco | Mitigação |
|---|---|
| Cloudflare Access/túnel fora do ar | Com a 443 fechada, contas locais do Hub e `akadmin` **não** são alcançáveis pela web e não mitigam essa falha. Caminho fora de banda obrigatório antes da Fase 3: SSH restrito por chave e origem administrativa (já exigido em `ecosystem-completion-plan.md`) com *port forward* para Caddy/Authentik, testado em exercício trimestral. Sem esse teste aprovado, a 443 não fecha. |
| Entra ID fora do ar | `akadmin` local no Authentik. |
| Authentik fora do ar | Backup testado (Tier 1), restore em < RTO de 4h (ADR 0004). |
| cloudflared crash | Systemd restart. Healthcheck monitora. |

## 11. Decisões delegadas ao builder

- Configuração exata do túnel cloudflared (config.yml, systemd unit).
- Políticas Access (OTP vs hardware key, sessão TTL).
- Ordem de migração das apps (Hub primeiro, depois GLPI, n8n, Zabbix).
- Se o WARP é obrigatório ou opcional para operadores (navegador sem WARP também funciona via túnel, mas perde ZTNA no dispositivo).