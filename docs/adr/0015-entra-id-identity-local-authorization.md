# ADR 0015 — Entra ID como provedor de identidade e autorização local nas aplicações

- Status: aceita
- Data: 05/11/2026
- Decisor: Ricardo Esper
- Substitui: [ADR 0007](0007-authentik-central-identity.md)

## Contexto

O ADR 0007 tornou o Authentik a identidade central. Em 05/11/2026 nenhuma aplicação estava homologada nele, o MFA dos administradores não estava comprovado e o baseline (`config/authentik/ness-os-baseline.yaml`) seguia `desired-not-applied`. Mesmo assim, o Authentik exige operação Tier 1: backup, restore, healthcheck, runbook e rotação de segredos.

A ness. migrou do Google Workspace para o Microsoft 365, e o Entra ID já identifica todos os operadores. Clientes acessarão somente o app ness.OS e os dashboards finais; não usarão Zabbix, GLPI ou n8n. Não há exigência de federação por tenant.

## Decisão

1. **Entra ID é o provedor de identidade** do ecossistema. Operadores usam a conta `@ness.com.br`. Usuários de clientes entram como convidados B2B (conta Microsoft, Google ou código por e-mail).
2. **O provedor autentica; a aplicação autoriza.** Papel e tenant de cada usuário ficam no banco da aplicação, cadastrados previamente por `platform_admin`. O vínculo é o par `issuer` + `oid`, nunca e-mail. Não há provisionamento JIT: identidade válida sem registro prévio é recusada.
3. **MFA:** operadores recebem Entra ID P1 com Acesso Condicional exigindo MFA em todo login. Convidados ficam sob as *security defaults*; MFA forte para cliente é revisado quando houver exigência contratual.
4. **Borda:** Cloudflare Access protege as ferramentas internas (GLPI, n8n e, quando aplicável, Zabbix web). O app ness.OS é publicado pelo túnel sem Access e autentica por conta própria, para que clientes não consumam a cota do Access.
5. **Quebra de vidro:** contas locais em Hub, Zabbix e GLPI, alcançáveis por SSH com *port forward*, mais duas contas de emergência no Entra excluídas do Acesso Condicional. Testadas trimestralmente.
6. **O Authentik será desligado** ao fim da migração. Até lá, continua sendo o caminho de login vigente e a UAT da Fase 1 é executada sobre ele.

## Sequência

1. Não alterar identidade antes do aceite do MVP e do gate da Fase 0.
2. Autorização local no Hub (papel e tenant no banco; claims de grupo ignorados).
3. Hub com OIDC Entra; Zabbix com SAML Entra.
4. Cloudflare Access + túnel na frente de GLPI e n8n.
5. Desligar o Authentik, manter backup por 30 dias e remover `sso.ness.com.br`.

Desenho detalhado: [`../superpowers/specs/2026-11-05-identity-access-perimeter-design.md`](../superpowers/specs/2026-11-05-identity-access-perimeter-design.md).

## Consequências

- O Authentik deixa de ser serviço Tier 1 após o desligamento; sai backup, runbook e rotação desse serviço.
- Custo recorrente novo: P1 para operadores (~US$ 6 por usuário/mês). Cloudflare Free cobre até 50 usuários do Access.
- Dependência da Microsoft para login; mitigada pela quebra de vidro local.
- Convidados de clientes existem no diretório corporativo da ness.: a colaboração externa deve restringir o acesso de convidados. Se o volume ou a regulação exigir, os clientes migram para um tenant External ID separado.
- Permanecem do ADR 0007: homologação por aplicação com testes negativos, MFA para administradores, menor privilégio e remoção de fluxos duplicados.
- O ADR 0013 permanece: `platform_admin` passa a ser atribuído no banco do Hub, não em grupo do provedor.
