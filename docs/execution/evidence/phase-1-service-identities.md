# Evidência de identidades técnicas — Fase 1

**Data:** 2026-09-27  
**Escopo:** inspeção estática do worktree local; nenhum container, VPS ou serviço externo foi consultado.

Esta evidência descreve declarações encontradas em `app/docker-compose.yml`, `app/.env.example` e `infra/secrets/README.md`. Ela não comprova quais credenciais estão instaladas, seu escopo efetivo, idade de rotação ou revogação.

| Serviço | Consumidor e origem declarados | Escopo observado | Idade e rotação |
|---|---|---|---|
| Zabbix | `api` e `worker-alerts`; `/etc/ness-os/zabbix-integration.env`; `NINF_ZABBIX_API_TOKEN` | Não verificável pelo código local | Não verificada |
| GLPI | `api` e `worker-alerts`; `/etc/ness-os/glpi-integration.env`; `NINF_GLPI_APP_TOKEN`, `NINF_GLPI_USER_TOKEN` | Não verificável pelo código local | Não verificada |
| Authentik | `authentik-server` e `authentik-worker`; variáveis do `.env`; `NINF_AUTHENTIK_SECRET_KEY` | Não verificável pelo código local | Não verificada |
| Banco de dados | `api`, `evolution`, Authentik e Postgres recebem `NINF_DB_PASSWORD` | Credencial compartilhada entre serviços declarada no Compose; separar usuários/escopos ainda é necessário | Não verificada |
| Psono | Recuperação administrativa descrita em `docs/runbooks/identity-break-glass.md` | Identidades técnicas não inventariadas localmente | Não verificada |
| n8n | `ninf-n8n`; variáveis de integração do `.env` e volume persistente `n8n-data` | SSO/RBAC de editor, executor e webhook requer validação no serviço | Não verificada |
| Contabo | `NINF_CONTABO_CLIENT_SECRET` e `NINF_CONTABO_API_PASSWORD` aparecem no exemplo de ambiente | O escopo read-only não é comprovado por nomes de variáveis | Não verificada |
| Object Storage | Nenhum consumidor/identidade foi confirmado nos arquivos inspecionados | Não configurado ou não evidenciado neste worktree | Não verificada |

## Pendências de evidência

- Obter inventário protegido de consumidores e contas técnicas ativas; registrar somente identificador, proprietário, escopo, origem segura e data da última rotação.
- Validar permissões efetivas de Zabbix e GLPI e separar credenciais compartilhadas entre serviços.
- Confirmar SSO/RBAC no n8n, inclusive acesso direto e webhooks, sem exportar credenciais ou logs sensíveis.
- Fazer rotação controlada de uma credencial não crítica e provar que a credencial anterior foi revogada.
- Confirmar se Object Storage tem consumidor ativo e uma identidade dedicada.

**Resultado:** inventário local parcial; identidade técnica, escopo e rotação em produção continuam **não verificados**. Não usar esta evidência como aprovação da Fase 1.
