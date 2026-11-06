# ADR 0015 — Entra ID como provedor de identidade e autorização local nas aplicações

- Status: aceita
- Data: 05/11/2026 · revisão de clareza: 06/11/2026 (sem mudança de decisão)
- Decisor: Ricardo Esper
- Substitui: [ADR 0007](0007-authentik-central-identity.md)

## A regra em uma frase

**O Entra ID diz quem a pessoa é. Cada sistema decide o que ela pode fazer. A Cloudflare só decide se ela chega à porta.**

Nenhum grupo, papel ou tenant é lido do Entra ID nem da Cloudflare. O Authentik **sai**.

## Contexto

O ADR 0007 tornou o Authentik a identidade central. Em 05/11/2026 nenhuma aplicação estava homologada nele, o MFA dos administradores não estava comprovado e o baseline (`config/authentik/ness-os-baseline.yaml`) seguia `desired-not-applied`. Mesmo assim, o Authentik exige operação Tier 1: backup, restore, healthcheck, runbook e rotação de segredos.

A ness. migrou do Google Workspace para o Microsoft 365, e o Entra ID já identifica todos os operadores. O tenant está em **Entra ID Free** (confirmado em 05/11/2026). Clientes acessarão somente o app ness.OS e os dashboards finais; não usarão Zabbix, GLPI, Wazuh, Psono nem n8n/Node-RED. Não há exigência de federação por tenant.

## Decisão

### Três camadas, três donos

| Camada | Pergunta | Dono | O que **não** faz |
|---|---|---|---|
| **Identidade** | Quem é você? | **Entra ID** (conta `@ness.com.br`; cliente como convidado B2B) | Não guarda papel, tenant nem grupo de aplicação |
| **Borda** | Você pode chegar à porta? | **Cloudflare Access + túnel**, só nas ferramentas internas | Não decide papel; não protege o app ness.OS |
| **Autorização** | O que você pode fazer aqui? | **Cada sistema, no próprio banco** | Não confia em claim de grupo vindo do provedor |

### Como cada sistema funciona (estado-alvo)

| Sistema | Quem acessa | Como entra | Onde ficam papel e grupos | Emergência |
|---|---|---|---|---|
| **ness.OS (Hub)** | Operadores e clientes | OIDC Entra, direto no app, pelo túnel **sem** Access | Banco do Hub: papel e tenant cadastrados antes por `platform_admin`, vínculo `issuer` + `oid` | Conta local do Hub, por SSH + *port forward* |
| **Zabbix** | Só operadores | SAML Entra | No Zabbix: usuários e grupos criados nele, sem JIT | Conta local do Zabbix |
| **GLPI** | Só operadores | Cloudflare Access (Entra) **e depois** login local do GLPI | No GLPI: perfis e entidades | Conta local do GLPI |
| **n8n / Node-RED** | Só operadores | Cloudflare Access (Entra) e login local | Na ferramenta | Conta local |
| **Wazuh (dashboard)** | Só operadores | Só pela tailnet, login local | No Wazuh (usuários internos) | `admin` do Wazuh, guardado no Psono |
| **Psono** | Só operadores | Login nativo do Psono, com 2FA dele | No Psono | Procedimento do próprio Psono |
| **API e webhooks** (`/webhook/*`, `/v1/alerts`, `/api/v1/alerts`) | Máquinas | Sem Access; `source-key` obrigatória; métodos impostos no Caddy | Não se aplica | Não se aplica |

Regras sem exceção:

1. **O provedor autentica; o sistema autoriza.** Identidade válida sem cadastro prévio no sistema é **recusada** (403 e log). Não há provisionamento JIT em nenhum sistema.
2. **O vínculo é `issuer` + `oid`, nunca e-mail.** O e-mail serve só para o primeiro vínculo, a partir de convite feito por `platform_admin`.
3. **Desativar no sistema corta o acesso**, mesmo com a conta Entra ativa.
4. **`platform_admin` é atribuído no banco do Hub** (ADR 0013), não em grupo do provedor.
5. **Clientes só entram no ness.OS.** Nunca recebem acesso a Zabbix, GLPI, Wazuh, Psono ou n8n/Node-RED.

### MFA

Sem licença adicional: P1 e P2 **não** serão contratados (decisão de 05/11/2026). Valem os *security defaults* do Entra, gratuitos, que exigem MFA de todos os usuários, administradores incluídos. **Não há Acesso Condicional.**

Consequências aceitas: não há política por população (operador × convidado); as contas de emergência do Entra não podem ser excluídas do MFA; MFA forte de cliente por contrato fica fora do escopo. Se um contrato exigir mais, é nova decisão de custo.

### Quebra de vidro

Contas locais em Hub, Zabbix e GLPI, alcançáveis por SSH + *port forward*, mais duas contas de emergência no Entra (MFA por chave FIDO2 ou autenticador guardados fora do computador). Testadas trimestralmente. A porta 443 só fecha depois desse teste.

### O que sai

- **Authentik**: `authentik-server`, `authentik-worker`, `sso.ness.com.br`, os blocos `forward_auth` do Caddy e os segredos dele.
- **Leitura de claims `groups` e `tenant_id`** no Hub.
- **JIT** em qualquer sistema.

## Hoje × alvo (em 06/11/2026)

| Sistema | Hoje em produção | Alvo |
|---|---|---|
| Hub | Autorização local já ativa (Fase A, `1175954`); código OIDC ainda aponta para o Authentik, sem uso real | OIDC Entra |
| Zabbix | SAML Authentik | SAML Entra |
| GLPI | `forward_auth` Authentik + `REMOTE_USER` | Access + login local |
| n8n | `forward_auth` Authentik | Access + login local (Node-RED na migração) |
| Wazuh | Login local; R3a ainda não aplicado | Igual, só pela tailnet |
| Psono | Login nativo | Igual |

**Até a Fase D, o Authentik continua sendo o login vigente**, e a UAT da Fase 1 roda sobre ele. Desligá-lo antes derruba o acesso a GLPI, n8n e Zabbix.

## Sequência

Nada desta sequência começa antes do aceite do MVP (UAT da Fase 1) e do gate da Fase 0.

| Fase | O que acontece | Estado |
|---|---|---|
| **A** | Autorização local no Hub (`issuer` + `oid`, sem JIT, sem claims de grupo) | **Em produção desde 05/11** |
| **B** | App OIDC do Hub no Entra; *security defaults*; 2 contas de emergência; colaboração externa restrita; 1 cliente piloto; Zabbix SAML Entra (UAT, depois produção) | Travada |
| **C** | `cloudflared` + Access em GLPI e n8n (remove `forward_auth`); Hub e API pelo túnel sem Access; teste da emergência; fechar a 443 | Travada |
| **D** | Desligar o Authentik; backup guardado 30 dias; remover `sso.ness.com.br`, o bloco do Caddy e os segredos | Travada |

Desenho detalhado: [`../superpowers/specs/2026-11-05-identity-access-perimeter-design.md`](../superpowers/specs/2026-11-05-identity-access-perimeter-design.md).

## Alternativas consideradas

| Alternativa | Por que não |
|---|---|
| Manter o Authentik como IdP central | Serviço Tier 1 a mais, nenhum app homologado, MFA não comprovado; o Entra já identifica todos os operadores |
| Authentik federado com o Entra | Duas peças para o mesmo papel; mantém todo o custo operacional do Authentik |
| Papel e tenant vindos de grupos do Entra | Exige P1 para grupos dinâmicos e ataria a autorização ao diretório corporativo; um erro no diretório viraria vazamento entre tenants |
| Cloudflare Access na frente do Hub | Cliente consumiria a cota de 50 usuários do Free; o Hub já autentica sozinho |
| Contratar Entra ID P1 (Acesso Condicional) | Custo recorrente sem exigência contratual hoje; *security defaults* cobrem MFA |

## Consequências

- O Authentik deixa de ser serviço Tier 1 após o desligamento; saem backup, runbook e rotação desse serviço.
- Sem custo recorrente novo: *security defaults* e Cloudflare Free (até 50 usuários no Access) bastam.
- Dependência da Microsoft para login; mitigada pela quebra de vidro local.
- Dupla autenticação em GLPI e n8n (Access + login local): aceita, porque são poucos operadores e o login local mantém a autorização no sistema.
- Convidados de clientes existem no diretório corporativo da ness.: a colaboração externa deve restringir o acesso de convidados. Se o volume ou a regulação exigir, os clientes migram para um tenant External ID separado.
- Permanecem do ADR 0007: homologação por aplicação com testes negativos, MFA para administradores, menor privilégio e remoção de fluxos duplicados.
