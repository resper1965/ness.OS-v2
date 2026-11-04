# ness.OS — trilha de execução realinhada (04/11)

Substitui só a **ordem** dos próximos passos. Escopo continua no [master](2026-10-12-ness-os-plano-master.md); tasks numeradas no [plano de execução](2026-10-26-ness-os-execution-plan.md) e no [plano GLPI](2026-10-12-glpi-ness-os-complete-delivery.md).

Ordem dos projetos (plano por projeto do Ricardo): P0 e P1 em paralelo → P2 → P3 → P5 (piloto Ionic Health) → P4 → P6 → P7.

## Trilha A — Zabbix → Hub fecha o ciclo (agora)
| Passo | Entrega | Estado |
|---|---|---|
| A1 | Recuperação ligada no Zabbix (ação 7, media 72) | feito 03/11 (#146) |
| A2 | Contador "abertos" ignora recuperados | feito (#149); frontend promovido em 04/11 (A4) |
| A3 | Backfill dos incidentes `problem` já recuperados — `infra/scripts/hub-zabbix-backfill.py` | feito em 04/11: 29.151 gravados, `status` intacto (evidência em `zabbix-hub-recovery-2026-11-03.md`) |
| A4 | Promover frontend com o contador novo | feito em 04/11: `ninf-frontend@sha256:f4afa04a…` (commit `1b76de6`); rollback = imagem `1051d84f…` no `.env` da release |

Aceite A3: `ninf_zabbix_status='problem'` só onde o Zabbix mantém o problema aberto; `status` intacto; ações `backfill` = incidentes com tag `ninf_zabbix_backfill`.

## Trilha B — SOC (P0 → P1 → P2)
| Passo | Estado |
|---|---|
| P0 Fundação SOC | feito, em produção `56c4659` |
| P1 contrato de sinais v1 | validado em 04/11 (#153, #160): consumidor independente passou; `docs/specs/signal-contract-v1-validacao.md` |
| P2 | prazos aceitos 04/11; primeiro corte backend na `main` (#161); falta vínculo decisão SOC ↔ incidente, mapeamento do `/secops/triage`, UI (espera redesenho) e o revisor da amostra semanal |
| Wazuh → Hub em produção | espera contratação e desenho de coleta (D3/D6) |

## Trilha C — GLPI (plano GLPI T06 → T14)
T05 e T06 fechadas para os 7 ativos e os 2 Fortigates. Restam: inventário restante (510 incidentes sem ativo), T07 agentes (diagnóstico feito em #152; piloto espera decisões do Ricardo), T08 atendimento/catálogo, T09 backlog. Regra: sem `callAsSystem`, salvo exceção do Ricardo para o lote dito. T07 e T08 têm ponto humano (piloto #79, SLA contratual).

## Trilha D — Fundação
Lockfile do backend (kombu #142); limpeza das senhas antigas nos `.env` das releases antigas; Action1 (avisar acima de 200 endpoints, hoje 1); #82 (3 ações do Ricardo).

## Só o Ricardo destrava
SLA/OT/revisor (P2), contratação Wazuh, HTML do redesenho (P6), três itens da #82.

## Regras da execução
Mudança em produção só com OK explícito do Ricardo, dito o efeito. PR de código passa por revisor Sonnet; comentários P1/P2 do Codex bloqueiam. Piso de severidade não é fixado; o 12 é a política aprovada em 03/11 (`soc-attendance-policy.md`).
