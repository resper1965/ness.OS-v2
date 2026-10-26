# Matriz de acesso do Hub (MVP)

Levantamento das rotas registradas em `app.main` em 2026-09-28. O backend usa os papéis persistidos `platform_admin`, `admin`, `operator`, `viewer`, `noc`, `soc`, `helpdesk`, `gestao` e `cliente`. Grupos Authentik `operator` e `viewer` são mapeados para papéis próprios, com tenant obrigatório no OIDC. O papel e o tenant são revalidados no servidor a cada requisição. Um `tenant_id` enviado pelo cliente não amplia o escopo dos papéis de tenant.

**Gate pendente para a Fase 1:** `noc`/`soc` mantêm acesso global nas rotas `require_noc`. `operator` e `viewer` ficam restritos ao próprio tenant em lista, detalhe e stream de incidentes; somente `operator` pode executar ações nesse escopo. A implementação local não substitui UAT no Authentik e nas aplicações integradas, MFA e recuperação.

| Política | Papéis / identidade | Escopo e negação |
|---|---|---|
| `platform_admin` | `platform_admin` | Plano de controle global; sem login: 401, papel errado: 403 |
| `noc` | `noc`, `soc`, `admin`, `platform_admin` | Operação global; sem login: 401, papel errado: 403 |
| `operator` | `operator` e papéis `noc` globais | Ações de incidente: `operator` somente no próprio tenant; outro tenant: 404; `viewer`: 403 |
| `viewer` | `viewer` | Leitura de incidentes somente no próprio tenant; outro tenant: 404 |
| `auth` | Qualquer conta ativa | Dados próprios ou tenant efetivo, conforme a rota; sem login: 401, tenant divergente: 403 |
| `source-key` | Chave técnica do webhook ou da API | Escopo do contrato da fonte; chave ausente/inválida: 401/403 conforme o verificador |

## Rotas do operador e do tenant

| Método e rota | Ação | Política e escopo |
|---|---|---|
| `GET /api/core/overview` | Resumo operacional | `noc`, global |
| `GET /api/core/modules` | Módulos disponíveis | `auth`, catálogo de módulos |
| `GET /api/core/kpis` | Indicadores operacionais | `noc`, global |
| `GET /api/dashboard/summary` | Resumo do painel | `noc`, global |
| `GET /api/dashboard/sources` | Estado e frescor das fontes | `noc`, global |
| `GET /api/dashboard/unified` | Painel unificado | `noc`, global |
| `GET /api/dashboard/problems` | Problemas do painel | `noc`, global |
| `GET /api/dashboard/pipeline-status` | Estado do pipeline | `noc`, global |
| `GET /api/incidents` | Listar incidentes | `auth`, tenant efetivo para `operator`, `viewer` e `cliente`; `noc` pode selecionar tenant |
| `GET /api/incidents/{incident_id}` | Detalhe, origem Zabbix e vínculo GLPI | `auth`, tenant efetivo para `operator`, `viewer` e `cliente`; incidente ausente ou fora do tenant: 404 |
| `POST /api/incidents/{incident_id}/actions` | Reconhecer, assumir, comentar, resolver ou encerrar com histórico | `operator` no próprio tenant ou `noc` global; `viewer`: 403; outro tenant: 404; transição inválida ou GLPI pendente: 409 |
| `POST /api/incident/analyze` | Analisar incidente | `noc`, global |
| `GET /api/incidents/stream` | Eventos de incidentes | `auth`, filtro de tenant para `operator`, `viewer` e `cliente`; revalida sessão, papel e tenant durante o stream |
| `GET /api/tenants/health` | Saúde dos tenants | `noc`, global |
| `GET /api/tenants/security-audit` | Auditoria de segurança | `noc`, global |
| `GET /api/tenants/list` | Listar tenants | `noc`, global |
| `GET /api/tenants/{tenant_id}/summary` | Resumo do tenant | `auth`, `resolve_tenant_scope`; divergência: 403 |
| `GET /api/assets/cmdb` | Ativos CMDB | `auth`, `resolve_tenant_scope`; divergência: 403 |
| `GET /api/assets/summary` | Resumo de ativos | `noc`, global |
| `GET /api/assets` | Ativos Atera | `noc`, global |
| `GET /api/assets/count` | Contagem de ativos | `noc`, global |
| `GET /api/rmm/atera/customers` | Clientes Atera | `noc`, global |
| `GET /api/rmm/atera/agents` | Agentes Atera | `noc`, global |
| `GET /api/rmm/atera/alerts` | Alertas Atera | `noc`, global |
| `GET /api/rmm/atera/summary` | Resumo Atera | `noc`, global |
| `GET /api/secops/cve-intel` | Inteligência de CVEs | `noc`, global |
| `GET /api/secops/zabbix-health` | Saúde Zabbix | `noc`, global |
| `GET /api/secops/triage-stats` | Estatísticas de triagem | `noc`, global |
| `POST /api/secops/triage` | Executar triagem | `noc`, global |
| `GET /api/secops/decisions` | Consultar decisões | `auth`, `resolve_tenant_scope`; divergência: 403 |
| `GET /api/auth/me` | Ler sessão atual | `auth`, usuário próprio |
| `POST /api/v1/push/subscribe` | Registrar inscrição push | `auth`, tenant do usuário |
| `POST /api/v1/push/unsubscribe` | Remover inscrição push | `auth`, inscrição do usuário |

## Plano de controle Contabo

Todas as rotas abaixo são somente leitura e exigem `platform_admin`; negam outros papéis com 403 e ausência de sessão com 401.

| Método e rota | Ação |
|---|---|
| `GET /api/contabo/compute` | Listar instâncias |
| `GET /api/contabo/compute/{instance_id}/snapshots` | Listar snapshots |
| `GET /api/contabo/storage` | Listar armazenamento |
| `GET /api/contabo/summary` | Resumo de recursos |
| `GET /api/contabo/firewall` | Listar firewalls |
| `GET /api/contabo/networks` | Listar redes |
| `GET /api/contabo/images` | Listar imagens |
| `GET /api/contabo/audits` | Listar auditorias |
| `GET /api/contabo/dashboard-full` | Painel completo |

## Entrada técnica e rotas públicas

| Método e rota | Controle e escopo |
|---|---|
| `POST /webhook/zabbix` | `source-key` do webhook Zabbix |
| `POST /webhook/glpi` | `source-key` do webhook GLPI |
| `GET /webhook/health` | `source-key` do webhook |
| `POST /v1/alerts` | `source-key` da API de alertas |
| `POST /api/v1/alerts` | Mesmo contrato, com prefixo `/api` |
| `POST /api/auth/login` | Público; valida credenciais e conta ativa |
| `POST /api/auth/logout` | Valida origem; se houver sessão válida, incrementa a versão de sessão no banco e invalida os tokens anteriores; limpa o cookie local mesmo com token já inválido |
| `POST /api/auth/oidc/callback` | Público; valida origem, código e token OIDC |
| `POST /api/auth/seed` | Público apenas com `NINF_DEBUG=true`; indisponível em produção |
| `GET /api/v1/push/config` | Público; configuração de inscrição |
| `GET /` | Público; identificação do serviço |
| `GET /ready` | Público; readiness da API, PostgreSQL, Redis da aplicação e broker Celery, sem detalhes de falha |

O teste `test_every_non_public_api_route_has_recognized_authorization` falha se uma nova rota de API não declarar guarda de usuário ou chave técnica. Isso verifica presença de controle; os testes de isolamento e revogação das Fases 1 e 6 verificam o comportamento efetivo.
