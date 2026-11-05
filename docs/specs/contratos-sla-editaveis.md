# Contratos e SLA editáveis (P3)

Nenhum prazo, janela, calendário ou ordem de escalonamento mora no código: tudo vem de tabelas do Hub, editáveis por API (decisão do Ricardo, 05/11). O SLA é **contratual**: a política pertence a um **contrato**.

## Modelo

- `n_infraops_contracts`: tenant, nome, modalidade (`managed|onsite|shared`), status (`draft|active|suspended|ended`), vigência (`starts_on`/`ends_on`), calendário, observações, `updated_at/by`. Um único ativo por tenant (índice parcial). O **padrão interno ness.** é a linha `is_default` (sem tenant, **`contractual=false`**, único); toda saída de prazo carrega essa marca.
- `n_infraops_sla_policies` (por contrato, UNIQUE `(contract_id, key)`): `severity`/`min_severity`/`has_tenant` (quem a política cobre), `ack_minutes` (janela de reconhecimento do P3, único campo consumido hoje), `tto_minutes`/`ttr_minutes` (**só armazenados**; o SLM do GLPI os lerá), calendário, `enabled`.
- `n_infraops_escalation_steps` (por contrato): `position`, `role`, `enabled`.
- `n_infraops_sla_calendars` / `_calendar_hours` (vários intervalos por dia) / `_holidays`: **compartilhados**, referenciados pelo contrato e pela política. Fuso por calendário (`zoneinfo`), padrão `America/Sao_Paulo`.
- `n_infraops_contract_changes`: antes/depois (JSONB) de toda alteração de SLA em contrato **ativo** (política, passo, contrato, status, e calendário/feriado/horário de qualquer contrato ativo que o use).

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
| no_client | sev ≥ 4, sem cliente | 600 min (1 dia útil) | — | comercial |

`comercial` = seg–sex 08:00–18:00 (como o P3 já fazia; o GLPI usa 08–20: **divergência a decidir**, valor não alterado). Passos: soc, noc, operator, admin. tto/ttr vêm da proposta de `docs/operations/glpi-t08-diagnostico.md` §6, **não contratual**. Os valores do `ack` são os do P3 aceitos em 04/11.

## Como editar

API `/api/v1/sla`: GET para operator+ (cliente/viewer: 403); escrita só `admin`/`platform_admin`.
`contracts` (POST/PUT, `POST …/status`), `contracts/{id}/policies/{key}` (PUT/DELETE), `contracts/{id}/escalation-steps/{position}` (PUT/DELETE), `calendars` (+ `/hours`, `/holidays/{data}`), `contracts/{id}/changes`, `contracts/modality-divergences`.
Regras: minutos 1..43200; weekday 0–6; início < fim; timezone válido; calendário em uso não apaga (409); transições `draft→active→suspended↔active→ended` (ended final; inválida = 409); ativar exige ≥1 política habilitada e calendário; dois ativos no mesmo tenant = 409; contrato ativo não fica sem política habilitada; o padrão não fica sem passo habilitado.

## Recomendações (ITIL 4 / ISO 20000), todas editáveis — não são contrato

Fuso `America/Sao_Paulo`; 24x7 para crítica/alta; pausa de SLA só em "Pendente" com motivo aprovado; SLA com override por cliente via contrato; escalonamento 50/80/100 % do prazo e fechamento automático Solucionado→Fechado em 7 dias com reabertura (ambos no GLPI, futuro; **valor atual no GLPI não verificado**).

## O que falta

- Tela de configuração de contratos (espera o redesenho).
- SLM do GLPI lendo tto/ttr/calendário do contrato; níveis 50/80/100 %.
- Fonte única da modalidade = contrato; `n_infraops_tenant_mappings.modality` (usado por `pipeline_health`) passa a derivar dele. Hoje não é tocado; `GET /contracts/modality-divergences` só sinaliza a diferença.
- Migração: `python -m app.migrate` cria e semeia (idempotente); banco novo usa `sql/001_schema.sql` (paridade testada).
