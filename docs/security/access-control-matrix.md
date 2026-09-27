# Matriz de controle de acesso da API

Matriz gerada contra as rotas `APIRoute` montadas por `app.main` em `app.api.routers`. O teste `test_mounted_api_routes_are_authenticated_and_documented` exige autenticação reconhecida em toda rota protegida e entrada para cada método/rota montado. Rotas de webhook e alertas fora de `app.api.routers` usam credenciais próprias e ficam fora deste inventário.

## Papéis e negações

| Papel/política | Acesso | Negação |
|---|---|---|
| `platform_admin` | Controle global da plataforma; inclui administração Contabo. | 401 sem sessão/token; 403 para papel insuficiente. |
| `admin` | Operação global NOC/SOC e administração local; sem privilégios exclusivos de `platform_admin`. | 401 sem sessão/token; 403 para papel insuficiente. |
| `noc` / `soc` | Operação global NOC/SOC, conforme `require_noc`. | 401 sem sessão/token; 403 para papel insuficiente. |
| `helpdesk` (`operator`) | Acesso autenticado limitado ao tenant associado quando a rota suporta escopo de tenant. Não recebe acesso global NOC automaticamente. | 401 sem sessão/token; 403 sem tenant, papel inadequado ou tentativa cross-tenant. |
| `gestao` | Acesso autenticado limitado ao tenant associado quando suportado. | 401 sem sessão/token; 403 sem tenant, papel inadequado ou tentativa cross-tenant. |
| `cliente` (`viewer`) | Acesso autenticado limitado ao próprio tenant e às rotas de leitura permitidas. | 401 sem sessão/token; 403 sem tenant, papel inadequado ou tentativa cross-tenant. |
| Público | Somente endpoints explicitamente públicos abaixo; sujeitos às validações próprias (origem, DEBUG ou OIDC). | 400/403 conforme precondição do endpoint. |

Papéis persistidos permanecem definidos por `UserRole`. Claim `operator` mapeia para `helpdesk`; `viewer` para `cliente`. Claims NOC/SOC permanecem explícitas. Usuários não NOC/SOC/admin/platform_admin exigem `tenant_id` válido; claim inválida ou ausente resulta em 403.

## Rotas montadas

| Método | Rota | Papel mínimo | Escopo | Negação esperada |
|---|---|---|---|---|
| GET | /api/core/overview | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/core/modules | Autenticado | Global | 401 |
| GET | /api/core/kpis | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/contabo/compute | platform_admin | Global | 401/403 |
| GET | /api/contabo/compute/{instance_id}/snapshots | platform_admin | Global | 401/403 |
| GET | /api/contabo/storage | platform_admin | Global | 401/403 |
| GET | /api/contabo/summary | platform_admin | Global | 401/403 |
| GET | /api/contabo/firewall | platform_admin | Global | 401/403 |
| GET | /api/contabo/networks | platform_admin | Global | 401/403 |
| GET | /api/contabo/images | platform_admin | Global | 401/403 |
| GET | /api/contabo/audits | platform_admin | Global | 401/403 |
| GET | /api/contabo/dashboard-full | platform_admin | Global | 401/403 |
| GET | /api/dashboard/summary | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/dashboard/unified | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/dashboard/problems | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/dashboard/pipeline-status | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/incidents | Autenticado | Tenant próprio; operadores globais conforme filtro | 401/403 |
| POST | /api/incident/analyze | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/incidents/stream | Autenticado | Tenant próprio; operadores globais conforme filtro | 401/403 |
| GET | /api/tenants/health | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/tenants/security-audit | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/tenants/list | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/tenants/{tenant_id}/summary | Autenticado | Próprio tenant; NOC/SOC/admin/platform_admin podem consultar globalmente | 401/403 |
| GET | /api/assets/cmdb | Autenticado | Tenant próprio; operadores globais conforme filtro | 401/403 |
| GET | /api/assets/summary | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/assets | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/assets/count | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/rmm/atera/customers | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/rmm/atera/agents | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/rmm/atera/alerts | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/rmm/atera/summary | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/secops/cve-intel | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/secops/zabbix-health | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/secops/triage-stats | noc/soc/admin/platform_admin | Global | 401/403 |
| POST | /api/secops/triage | noc/soc/admin/platform_admin | Global | 401/403 |
| GET | /api/secops/decisions | Autenticado | Tenant próprio; operadores globais conforme filtro | 401/403 |
| POST | /api/auth/login | Público | Autenticação de credenciais; origem validada em browser | 401 credenciais inválidas; 403 conta inativa/origem inválida |
| GET | /api/auth/me | Autenticado | Próprio usuário | 401 |
| POST | /api/auth/logout | Público | Próprio cookie; origem confiável obrigatória | 403 origem inválida |
| POST | /api/auth/seed | Público condicionado | Criação idempotente somente com DEBUG e segredo configurados | 403 DEBUG desligado; 503 segredo ausente |
| POST | /api/auth/oidc/callback | Público condicionado | Identidade autenticada pelo OIDC e claims normalizadas | 400/401/403 conforme falha OIDC/claims |
| GET | /api/v1/push/config | Público | Configuração pública de push | — |
| POST | /api/v1/push/subscribe | Autenticado | Próprio usuário | 401 |
| POST | /api/v1/push/unsubscribe | Autenticado | Próprio usuário | 401 |
