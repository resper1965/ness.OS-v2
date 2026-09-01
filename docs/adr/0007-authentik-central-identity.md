# ADR 0007 — Authentik como identidade central

- Status: aceita
- Data: 20/08/2026
- Decisor: Ricardo Esper

## Contexto

O ecossistema utiliza OIDC, SAML, JWT local, API keys e logins locais. Authentik já está instalado, mas está apenas parcialmente funcional. A integração com Hub, Zabbix, GLPI e n8n não pode ser considerada pronta apenas pela presença de providers, clients ou configuração histórica.

## Decisão

Authentik será a identidade central obrigatória para usuários como estado-alvo. Cada aplicação será revisada diretamente e homologada de forma independente, usando OIDC ou SAML conforme o suporte efetivo. Administradores usarão MFA e contas locais existirão apenas para break-glass.

## Consequências

- Authentik torna-se serviço Tier 1 e precisa de backup, restore, healthcheck e runbook.
- Hub, Zabbix, GLPI e n8n serão classificados como `não configurado`, `parcial`, `homologado` ou `bloqueado`, com evidências por aplicação.
- A homologação inclui login, logout, expiração, revogação, desativação de usuário, claims, grupos/roles e testes negativos.
- Indisponibilidade do SSO não pode impedir recuperação administrativa.
- Grupos e papéis serão definidos centralmente e propagados com menor privilégio.
- Segredos OIDC default e fluxos de autenticação duplicados devem ser removidos.
