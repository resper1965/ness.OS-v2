# Identidade, acesso e perímetro — ness.OS

- **Status:** aprovado; execução após aceite do MVP e gate da Fase 0
- **Data:** 2026-11-05 (revisado no mesmo dia: Authentik sai)
- **Decisão:** [ADR 0015](../../adr/0015-entra-id-identity-local-authorization.md), que substitui o ADR 0007

## 1. Intenção

Simplificar identidade e perímetro: um provedor de identidade que a ness. já paga (Entra ID), autorização dentro das aplicações, ferramentas internas atrás do Cloudflare Access e nenhuma porta 443 pública na VPS AIOps. O Authentik sai.

## 2. Contexto

- A ness. migrou Google Workspace → Microsoft 365. Operadores têm conta `@ness.com.br` no Entra ID (plano Free hoje).
- A ness. é gestora da plataforma. Clientes acessam **somente o app ness.OS e os dashboards finais**. Zabbix, GLPI e n8n são só da ness.
- Authentik (ADR 0007): nenhuma aplicação homologada, baseline `desired-not-applied`, custo Tier 1 sem benefício entregue.
- Hub hoje: OIDC via Authentik; papel vem do claim `groups` e tenant do claim `tenant_id`, com JIT (`app/backend/app/api/routers/auth.py`).
- GLPI e n8n: `forward_auth` do Authentik no Caddy. Zabbix: SAML do Authentik (UAT).
- Perímetro: 443 aberta na VPS AIOps; Zabbix em outra VPS, com 10051 aberta para agentes.

## 3. Objetivos

1. Entra ID como único provedor de identidade (operadores e clientes).
2. Autorização local no Hub: papel e tenant no banco, sem depender de claims de grupo.
3. MFA em todo login via *security defaults* do Entra (sem licença adicional).
4. GLPI e n8n atrás do Cloudflare Access; 443 fechada na VPS AIOps.
5. Desligar o Authentik.

## 4. Fora do escopo

- Federação por tenant (cada cliente com seu próprio IdP).
- Magic WAN, Magic Transit, WAF.
- Intune, Defender, PIM, Identity Protection.
- Fechar a 10051 do Zabbix (o protocolo exige).

## 5. O que não pode acontecer

- Login sem registro prévio no Hub criar usuário ou conceder papel.
- Cliente alcançar GLPI, n8n ou Zabbix.
- Perder acesso administrativo quando a Microsoft ou o Cloudflare caírem.
- Executar qualquer etapa antes do aceite do MVP e do gate da Fase 0.

## 6. Desenho

```
Operador ──► Cloudflare Access (allow @ness.com.br) ──► túnel ──► Caddy ──► GLPI / n8n
Operador ┐
Cliente  ┴─► túnel (sem Access) ──► Caddy ──► Hub ──OIDC──► Entra ID
                                               └─► papel + tenant no banco do Hub
Operador ──► Zabbix web ──SAML──► Entra ID
Agentes  ──► Zabbix :10051 (inalterado)
Emergência ──► SSH (chave + origem restrita) ──port forward──► Hub / GLPI / Zabbix (contas locais)
```

### 6.1 Identidade (Entra ID)

| População | Como entra | MFA |
|---|---|---|
| Operadores | Membro `@ness.com.br` | *Security defaults* (MFA para todos) |
| Clientes | Convidado B2B (Microsoft, Google ou código por e-mail) | *Security defaults*; sem Acesso Condicional (decisão de 05/11: sem licenciamento). MFA forte por contrato fica fora do escopo |
| Emergência | 2 contas no Entra (sujeitas ao MFA; chave guardada fora do computador) + contas locais por app | Senha longa em cofre; uso auditado |

Colaboração externa: restringir convidados (sem enumerar diretório; sem acesso a Teams/SharePoint por padrão). Se o volume ou a regulação exigir, mover clientes para um tenant External ID separado (grátis até 50 mil MAU).

### 6.2 Autorização local no Hub

- Tabela de usuários guarda `issuer`, `oid`, papel e tenant. Vínculo por `issuer` + `oid`; e-mail é só exibição.
- `platform_admin` cadastra o usuário (e-mail de convite, papel, tenant) antes do primeiro login. No primeiro login, o `oid` é ligado ao registro pelo e-mail do convite e o vínculo fica fixo.
- Claim `groups` e `tenant_id` deixam de ser lidos. Sem JIT.
- Identidade válida sem registro → 403 e log.
- Desativar no Hub corta acesso mesmo com conta Entra ativa; `session_epoch` continua valendo.
- Papéis e regras de tenant existentes (`operator`, `viewer`, `platform_admin` etc.) não mudam.

#### 6.2.1 Grupos e papéis

Os grupos deixam de existir no provedor de identidade. O Entra ID só prova quem é a pessoa, e o grupo vira o **papel** gravado no registro do usuário no Hub. Motivos: o Entra Free não atribui grupos a aplicações (exige P1), manda grupos como GUID e não tem claim de tenant.

Cada usuário tem **um** papel e, se o papel for de cliente, **um** tenant. Os papéis são os do enum `UserRole` (`app/backend/app/models/users.py`), e o antigo grupo do Authentik vira o papel de mesmo nome:

| Papel (grupo Authentik antigo) | Quem | Escopo | Acesso no Hub |
|---|---|---|---|
| `platform_admin` (`platform_admin`, `ness-os-platform-admin`) | Gestor da plataforma (ness.) | Global | Plano de controle: cadastra usuários, papéis e tenants, com auditoria (ADR 0013) |
| `admin` (`admin`) | Operador sênior (ness.) | Global | Administração delegada e todas as rotas `noc` |
| `noc` (`noc`) | Operação de disponibilidade (ness.) | Global; pode selecionar o tenant | Painéis, ativos, triagem, incidentes de todos os tenants |
| `soc` (`soc`) | Operação de segurança (ness.) | Global | Igual a `noc` (gate `noc` aceita `soc`) |
| `helpdesk` (`helpdesk`) | Operação ITSM (ness.) | Hoje exige tenant (fora de `NOC_ROLES`) | A definir na matriz de acesso antes da Fase A |
| `gestao` (`gestao`) | Gestão e indicadores (ness.) | Hoje exige tenant (fora de `NOC_ROLES`) | A definir na matriz de acesso antes da Fase A |
| `operator` (`operator`) | Usuário do cliente que age | Um tenant | Incidentes do próprio tenant: ler e agir. Outro tenant = 404 |
| `viewer` (`viewer`) | Usuário do cliente só leitura | Um tenant | Incidentes do próprio tenant, só leitura. Ação = 403 |
| `cliente` (`usuarios`) | Usuário final do cliente | Um tenant | Dashboards finais do próprio tenant |

Regras:
- Papéis globais (`NOC_ROLES` em `app/backend/app/core/dependencies.py`: `platform_admin`, `admin`, `noc`, `soc`) só para membros `@ness.com.br`. Convidado B2B só recebe `operator`, `viewer` ou `cliente`, e sempre com tenant. O Hub recusa a combinação errada ao cadastrar e ao logar.
- Papel de tenant sem tenant = cadastro recusado. Papel global com tenant = tenant ignorado.
- MFA segue a seção 6.1 (*security defaults*). Eles não garantem MFA em todo login de `platform_admin`/`admin` do Hub, porque só valem para papéis de administrador do próprio Entra. Se isso for exigido, é preciso P1 só para esses usuários.
- Mudar papel ou tenant incrementa o `session_epoch`, e as sessões abertas caem.
- Só `platform_admin` muda papéis. Ninguém altera o próprio papel.
- A matriz de acesso (`docs/security/access-control-matrix.md`) continua sendo a fonte das permissões por rota. Esta tabela só resume.
- Na Fase A, `map_authentik_role` e `_AUTHENTIK_GROUP_ROLE_PRIORITY` (`app/backend/app/api/routers/auth.py`) são removidos. Para migrar os usuários, o papel atual de cada um é copiado para o banco uma vez.

Fora do Hub, cada ferramenta usa os próprios grupos, mantidos à mão porque só operadores da ness. as acessam:

| Ferramenta | Onde fica o grupo |
|---|---|
| Zabbix | Grupos de usuário do Zabbix. O SAML Entra só autentica, e o usuário é criado antes no Zabbix (sem JIT) |
| GLPI | Perfis do GLPI |
| n8n | Papéis do n8n |
| Cloudflare Access | Lista de e-mails `@ness.com.br` por aplicação, sem grupos do Entra |

### 6.3 Aplicações

| App | Hoje | Depois |
|---|---|---|
| Hub | OIDC Authentik, claims de grupo, JIT | OIDC Entra, autorização local |
| Zabbix | SAML Authentik (UAT) | SAML Entra; usuários e grupos no Zabbix, sem JIT; conta local de emergência |
| GLPI | `forward_auth` Authentik | Cloudflare Access + login local GLPI. OIDC nativo só se houver necessidade |
| n8n | `forward_auth` Authentik | Cloudflare Access + login local n8n |

### 6.4 Borda (Cloudflare)

- `cloudflared` na VPS AIOps, outbound-only. Firewall: 443 fechada após o gate de emergência.
- Access: aplicações GLPI e n8n (e Zabbix web, se for movido para o túnel), política `@ness.com.br` via Entra. Até 50 usuários no Free.
- Hub: pelo túnel, **sem** Access.

Caminhos que não podem passar por Access (máquina ou servidor-a-servidor):

| Caminho | Tratamento |
|---|---|
| `POST /webhook/zabbix`, `/webhook/glpi`, `GET /webhook/health`, `POST /v1/alerts`, `/api/v1/alerts` | Estão no host da API, sem Access. Métodos impostos no Caddy (demais = 405); `source-key` continua obrigatório. Teste negativo: método errado = 405, sem chave = 401 |
| `apirest.php` do GLPI (AIOps → GLPI) | Rota privada na rede Docker, nunca pelo Access nem pela internet |
| OIDC servidor-a-servidor (Hub → Entra) | Saída para a Microsoft; sem impacto do túnel |
| SSE e PWA | Pelo túnel; testar conexão longa e renovação de sessão no celular |
| Evolution e webhooks de terceiros | Mapear antes de fechar a 443 |

## 7. Sequência

```
Fase A — Autorização local no Hub (código; pode ser preparada antes, só entra em produção após o MVP)
  1. Modelo: issuer + oid, papel e tenant cadastrados; remover JIT e leitura de groups/tenant_id
  2. Tela/API de cadastro de usuário restrita a platform_admin, com auditoria (ADR 0013)
  3. Testes: sem registro = 403; tenant cruzado = 403; desativado = 401; vínculo por oid, não por e-mail

Fase B — Entra ID
  4. App registration OIDC para o Hub; *security defaults* ligados; 2 contas de emergência
  5. Colaboração externa restrita; convidar 1 cliente piloto
  6. Zabbix SAML Entra no UAT, depois produção

Fase C — Borda
  7. cloudflared + Access em GLPI e n8n (remover forward_auth do Caddy)
  8. Hub e API pelo túnel sem Access
  9. Gate: emergência por SSH + port forward testada em Hub, GLPI e Zabbix
  10. Fechar 443 na VPS AIOps

Fase D — Desligamento
  11. Desligar Authentik; backup guardado 30 dias; remover sso.ness.com.br e o bloco do Caddyfile
  12. Remover segredos do Authentik do cofre e dos .env
```

## 8. Custos

| Item | Mensal |
|---|---|
| Entra ID (security defaults, sem P1) | US$ 0 |
| Convidados B2B (até 50 mil MAU) | US$ 0 |
| Cloudflare Access/Tunnel (≤50 usuários) | US$ 0 |
| Authentik (sai) | menos operação Tier 1 |

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Microsoft fora do ar | Contas locais por SSH + port forward |
| Cloudflare fora do ar | Idem; a 443 só fecha após esse teste |
| Convidado vê dados do diretório da ness. | Restrição de colaboração externa; tenant External ID separado se preciso |
| Vínculo errado de identidade | `issuer` + `oid`; e-mail só no primeiro vínculo, a partir de convite feito por `platform_admin` |
| Regressão de isolamento por tenant | Repetir os testes negativos da Fase 1 com o novo modelo |

## 10. Decisões deixadas ao executor

- Forma da tela de cadastro de usuários no Hub.
- TTL de sessão no Access e no Hub.
- Se o Zabbix web entra no túnel ou mantém o registro A atual.
