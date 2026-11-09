# Contratos e SLA editáveis (P3)

Nenhum prazo, janela, calendário ou ordem de escalonamento mora no código: tudo vem de tabelas do Hub, editáveis por API (decisão do Ricardo, 05/11). O SLA é **contratual**: a política pertence a um **contrato**.

## Modelo

- `n_infraops_contracts`: tenant, nome, modalidade (`managed|onsite|shared`), status (`draft|active|suspended|ended`), vigência (`starts_on`/`ends_on`), calendário, observações, `updated_at/by`. Um único ativo por tenant (índice parcial). O **padrão interno ness.** é a linha `is_default` (sem tenant, **`contractual=false`**, único); toda saída de prazo carrega essa marca.
- `n_infraops_sla_policies` (por contrato, UNIQUE `(contract_id, key)`): `severity`/`min_severity`/`has_tenant` (quem a política cobre), `ack_minutes` (janela de reconhecimento do P3, único campo consumido hoje), `tto_minutes`/`ttr_minutes` (**só armazenados**; o SLM do GLPI os lerá), calendário, `enabled`.
- `n_infraops_escalation_steps` (por contrato): `position`, `role`, `enabled`.
- `n_infraops_sla_calendars` / `_calendar_hours` (vários intervalos por dia) / `_holidays`: **compartilhados**, referenciados pelo contrato e pela política. Fuso por calendário (`zoneinfo`), padrão `America/Sao_Paulo`.
- `n_infraops_contract_changes`: antes/depois (sem `notes`; transições, inclusive para `suspended`, são gravadas só como transição de status) (JSONB) de toda alteração de SLA em contrato **ativo** (política, passo, contrato, status, e calendário/feriado/horário de qualquer contrato ativo que o use).

## Resolução (a cada ciclo da varredura, sem cache)

1. Contrato `active` do tenant do incidente e vigente hoje (no fuso do contrato).
2. Senão, o contrato padrão.
3. Contrato do tenant **sem política habilitada para a classe** do incidente: **não herda em silêncio**; cai no padrão e registra WARNING com contrato e severidade.
4. `draft`/`suspended`/`ended` ou fora da vigência = inexistente.
5. Passos de escalonamento: os do contrato; sem nenhum habilitado, os do padrão.
6. Piso de severidade = menor severidade coberta por política habilitada (padrão + contratos vigentes). Sem política habilitada: a varredura não avisa e loga WARNING.

## Valores semeados (padrão interno, NÃO contratual)

| classe | cobre | ack | tto / ttr | calendário |
|---|---|---|---|---|
| critical | sev 5, com cliente | 15 min | 15 min / 4 h | 24x7 |
| elevated | sev 4, com cliente | 60 min | 30 min / 8 h | 24x7 |
| no_client | sev ≥ 4, sem cliente | 720 min (1 dia útil de 12 h) | — | comercial |

`comercial` = seg–sex 08:00–20:00, `America/Sao_Paulo` (**decisão do Ricardo em 05/11**; o calendário padrão do GLPI também é 08–20). Mudança intencional: o P3 em produção ainda roda 08–18/600 min até a próxima promoção, e o `ack` do sem cliente passou de 600 para 720 min para continuar significando "1 dia útil". Passos: soc, noc, operator, admin. tto/ttr vêm da proposta de `docs/operations/glpi-t08-diagnostico.md` §6, **não contratual**. Os `ack` de crítica e alta são os do P3 aceitos em 04/11.

## Como editar

API `/api/v1/sla`: GET para operator+ (cliente/viewer: 403); escrita só `admin`/`platform_admin`.
**Isolamento de tenant nas leituras:** NOC/admin leem tudo; `operator` com tenant lê só o próprio contrato (comparação sem diferenciar maiúsculas), a trilha dele e o contrato padrão (a trilha do padrão é só NOC); contrato de outro tenant responde 404; `operator` sem tenant, 403. Calendários não têm dono de tenant e são legíveis por operator+.
`contracts` (POST/PUT, `POST …/status`), `contracts/{id}/policies/{key}` (PUT/DELETE), `contracts/{id}/escalation-steps/{position}` (PUT/DELETE), `calendars` (+ `/hours`, `/holidays/{data}`), `contracts/{id}/changes`, `contracts/modality-divergences`.
Regras: `tenant_id` é normalizado (`lower().strip()`) e a unicidade de contrato ativo é por `lower(tenant_id)`; `PUT` com `null` em campo obrigatório = 422; `notes` até 4000 caracteres e **fora da trilha e do log**; passos só com soc/noc/operator/admin; intervalos do mesmo dia não podem se sobrepor (encostar é válido); minutos 1..43200; weekday 0–6; início < fim; timezone válido; calendário em uso não apaga (409); transições `draft→active→suspended↔active→ended` (ended final; inválida = 409); ativar exige ≥1 política habilitada e calendário; dois ativos no mesmo tenant = 409; contrato ativo não fica sem política habilitada; o padrão não fica sem passo habilitado.

## Recomendações (ITIL 4 / ISO 20000), todas editáveis — não são contrato

Fuso `America/Sao_Paulo`; 24x7 para crítica/alta; pausa de SLA só em "Pendente" com motivo aprovado; SLA com override por cliente via contrato; escalonamento 50/80/100 % do prazo e fechamento automático Solucionado→Fechado em 7 dias com reabertura (ambos no GLPI, futuro; **valor atual no GLPI não verificado**).

## O que falta

- Tela de configuração de contratos (espera o redesenho).
- SLM do GLPI lendo tto/ttr/calendário do contrato; níveis 50/80/100 %.
- Migração: `python -m app.migrate` cria e semeia (idempotente); banco novo usa `sql/001_schema.sql` (paridade testada).

## Regras de grupo de hosts e contatos do cliente

- `n_infraops_hostgroup_rules(pattern, customer_id, ignore_when_with_customer_id, priority)`: regra com `pattern` mapeia o nome exato do grupo (ex.: `Zabbix servers`) para um cliente; regra sem `pattern` descarta `customer_id` quando `ignore_when_with_customer_id` também casa (par Alupar × Alupar PE/CO). O padrão `[ X ]` segue pelo cadastro de apelidos. Constraints: `pattern` não vazio e regra não aponta para si mesma. Regra que aponta para cliente inativo é ignorada (sem fallback); ambiguidade recusa o ticket.
- **O seed das regras só roda com a tabela vazia** (`WHERE NOT EXISTS`): edição ou remoção de regra não é desfeita pela migração, mas apagar todas as regras e migrar de novo as recria.
- `n_infraops_customer_contacts` + `/api/customers/{id}/contacts`: escrita `admin`/`platform_admin`, leitura só NOC global (`noc`/`soc`/`admin`/`platform_admin`; `operator` é escopado a tenant e recebe 403). Dado pessoal: log e trilha guardam só ids e nomes de campo; erro de banco no router vira 500 genérico e o engine usa `hide_parameters=True`. Nada consome os contatos ainda.

## Modalidade efetiva e parâmetros da política de atendimento

**Modalidade.** `services.sla.effective_modality(session, tenant)` = modalidade do contrato `active` e vigente (no fuso do calendário); senão a do mapeamento (`n_infraops_tenant_mappings`); senão `None`. Contrato `draft`/`suspended`/`ended` ou fora da vigência é inexistente. `pipeline_health.source_coverage` usa essa regra por vínculo (a cobertura declarada continua só para valor não nulo) e devolve `modality_divergence` por fonte; nada é escrito no mapeamento. `GET /contracts/modality-divergences` segue disponível.

**Parâmetros por contrato** (`n_infraops_contract_policy_params`, `(contract_id, key)`; `GET/PUT/DELETE /api/v1/sla/contracts/{id}/params[/{key}]`, escrita `admin`/`platform_admin`, leitura `operator`+ com o mesmo isolamento de tenant dos contratos; trilha em `contract_changes`, entidade `policy_param`). Resolução a cada chamada, sem cache: contrato ativo vigente do tenant → linha do contrato padrão (**não contratual**) → constante de código. `get_param(session, tenant, key) -> ParamValue(value, contractual)`.

| chave | padrão | limite | uso |
|---|---|---|---|
| `soc_attend_min_level` | 12 | **máx. 12** (422 acima) | piso de atendimento do Wazuh; efetivo = `min(contrato, 12)` |
| `soc_archive_score_floor` | 75 | máx. 75 | limiar de score abaixo do qual arquiva |
| `ot_retrospective_hours` | 24 | máx. 24 (422 acima) | janela retrospectiva OT (ainda sem consumidor: regra 6 não existe) |
| `weekly_sample_per_client` | 20 | mín. 20 | amostra semanal por cliente |
| `weekly_sample_pct` | 10 | 10..100 | % do volume quando passa do limiar |
| `weekly_sample_threshold` | 200 | — | arquivados/semana a partir dos quais vale o % |

O contrato só pode **endurecer** a política (política SOC, "O contrato do cliente prevalece quando é mais exigente"): nível/score menor atende mais, janela menor revisa mais, amostra maior revisa mais. O banco repete o teto num `CHECK`. Valor de teto/piso não é contratual, é a política aprovada de 03/11. `GET …/params` mostra gravado, efetivo, padrão e limite; `contractual=false` quando o contrato é o padrão interno. Leitura que falha (tabela ausente, banco) cai nos padrões com WARNING, em SAVEPOINT, sem abortar a triagem.

`NINF_SOC_ATTENDANCE_MIN_LEVEL` foi removida: o padrão agora é a linha semeada do contrato padrão (12), editável.

**Amostra semanal.** `GET /api/secops/archived-sample` agrupa por cliente: cota = `weekly_sample_per_client` (20) ou, acima de `weekly_sample_threshold` (200) arquivados na janela, `ceil(weekly_sample_pct %)` do volume. A cota efetiva é o maior valor entre a calculada com os parâmetros do contrato e a calculada com os padrões (20 / 10 % / 200): nenhuma combinação de `per_client`, `pct` e `threshold` fica abaixo da política padrão. `limit` (opcional) é teto por cliente, não regra. A resposta ganha `groups` (arquivados, cota, amostrados e `contractual` por cliente; alertas sem cliente na chave `sem_cliente`); `items` mantém o formato.

**Parâmetros globais** (`n_infraops_platform_params`; `GET/PUT /api/v1/sla/platform-params`, leitura NOC, **escrita só `platform_admin`**; a medição é `scope: global`, sem tenant): `source_max_age_seconds` 900, `queue_max_age_seconds` 300, `worker_failure_window_seconds` 900, `probe_timeout_seconds` 20 (máx. 22, também em `CHECK`: leitura dos parâmetros (5 s) + sonda + cobertura (5 s) precisam caber nos 35 s do `hub-integration-monitor.sh`). Lidos a cada ciclo de `pipeline_health`; banco indisponível = padrões. Mudança só registrada em log estruturado (sem tabela de trilha: não pertence a contrato).

Valor acima de 2147483647 (INTEGER) = 422. Parâmetros não são dado pessoal do cliente. Fora: tela, consumo de `ot_retrospective_hours`, SLM do GLPI.

## Fechamento do plano de dados por cliente (Task 6, 09/11/2026)

### Modelo final

| tabela | propósito | constraints principais |
|---|---|---|
| `n_infraops_customers` | identidade do cliente, glpi_entity_id, active | `key` UNIQUE |
| `n_infraops_customer_aliases` | apelidos normalizados (`lower().strip()`) | `alias_norm` UNIQUE, FK cascade |
| `n_infraops_hostgroup_rules` | regra `[Cliente]` como dado (pattern, ignore_when_with) | `pattern` não vazio, não aponta para si |
| `n_infraops_customer_contacts` | e-mail/telefone do plantão do cliente | `notify_severity_min` 1–5, dado pessoal não em log |
| `n_infraops_contracts` | contrato por tenant (modalidade, vigência, status) | 1 ativo por `lower(tenant_id)`, `is_default` sem tenant |
| `n_infraops_sla_policies` | prazos por classe/severidade | UNIQUE `(contract_id, key)` |
| `n_infraops_escalation_steps` | ordem de escalonamento por papel | posição única |
| `n_infraops_sla_calendars` / `_hours` / `_holidays` | calendários compartilhados com timezone | intervalos não se sobrepõem |
| `n_infraops_contract_changes` | trilha de toda mudança em contrato ativo | JSONB antes/depois, entidade `policy_param`, `customer`, `hostgroup_rule` |
| `n_infraops_contract_policy_params` | parâmetros SOC por contrato | `value_int > 0`, teto por chave (12/75/24/20/10-100) |
| `n_infraops_platform_params` | parâmetros globais (frescor, fila, probe) | `value_int > 0`, probe ≤ 22 |

### Chaves de policy_params

| chave | padrão | teto/piso | CHECK |
|---|---|---|---|
| `soc_attend_min_level` | 12 | ≤ 12 | `value_int <= 12` |
| `soc_archive_score_floor` | 75 | ≤ 75 | `value_int <= 75` |
| `ot_retrospective_hours` | 24 | ≤ 24 | `value_int <= 24` |
| `weekly_sample_per_client` | 20 | ≥ 20 | `value_int >= 20` |
| `weekly_sample_pct` | 10 | 10–100 | `value_int BETWEEN 10 AND 100` |
| `weekly_sample_threshold` | 200 | — | `value_int > 0` |

### Chaves de platform_params

| chave | padrão | CHECK |
|---|---|---|
| `source_max_age_seconds` | 900 | `value_int > 0` |
| `queue_max_age_seconds` | 300 | `value_int > 0` |
| `worker_failure_window_seconds` | 900 | `value_int > 0` |
| `probe_timeout_seconds` | 20 | `value_int <= 22` |

### O que continua fora

- Tela de configuração de contratos (espera o redesenho, Task 4 do plano de aceleração).
- SLM do GLPI (tto/ttr/calendário do contrato, níveis 50/80/100 %).
- Consumo dos contatos do cliente (tabela existe, API existe, nada chama).
- Consumo de `ot_retrospective_hours` (regra 6 do SOC ainda não existe).
- Revisão semanal automatizada (quem revisa a amostra, quando).
- Remoção dos cards de exemplo do SecOps (`secops.py:41-185`; conteúdo de demonstração).

### Checklist de promoção

- [x] Migração aditiva idempotente (`migrate.py` + `sql/001_schema.sql`, paridade testada).
- [x] Seeds com `ON CONFLICT DO NOTHING`: 13 clientes, 22 apelidos, 3 políticas, 4 passos.
- [x] Regras de grupo de hosts semeadas (comportamento idêntico ao código antigo).
- [x] Comportamento atual idêntico ao antigo: suíte `test_alert_glpi_idempotency.py` verde.
- [x] `resolve_glpi_entity_id` assíncrono, chama `services.customers`.
- [x] `customer_from_hostgroups` consulta tabela, não dicionário em código.
- [x] `effective_modality` contrato → mapeamento → None.
- [x] `get_param` contrato ativo → padrão → constante; `contractual=false` no padrão.
- [x] `archived_sample` agrupado por cliente, maior cota entre contrato e padrão.
- [ ] Sem tela de contratos (espera redesenho).
