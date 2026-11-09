# Padrões operacionais propostos

> Task 1 do [plano de aceleração](../superpowers/plans/2026-11-05-acelerar-producao.md).
> Todos são `contractual=false`, internos, editáveis depois pela tela de contratos.

| Item | Padrão proposto | Onde é editável | Se o Ricardo não responder em 24 h |
|---|---|---|---|
| Revisor da amostra semanal | Papel `soc` de plantão, segunda-feira 09:00 BRT | `n_infraops_contract_policy_params`, chave pendente | Segue com seed em ambiente de teste, **não** promove |
| Calendário padrão | 24×7 para severidade 4 e 5; **08–20 BRT** dias úteis para o resto (decisão do Ricardo em 05/11; já é o `comercial` em produção), feriados nacionais do ano | Calendários do contrato (`n_infraops_sla_calendars`) | idem |
| Escalonamento | 50/80/100 % do prazo, papéis padrão | `n_infraops_escalation_steps` | idem |
| Pausa do SLA | Só em status "Pendente" com motivo aprovado | Política do contrato (campo pendente no GLPI) | idem |
| Fechamento automático | Solucionado → Fechado em 7 dias, com reabertura | Configuração do GLPI (valor atual não verificado) | idem |
| Janela OT retrospectiva | 24 h (teto da política SOC) | `ot_retrospective_hours`, máx. 24 | idem |
| Plantão | Ordem atual por papel `soc` → `noc` → `operator` → `admin` até haver fonte de escala real | `n_infraops_escalation_steps` (contrato padrão) | idem |

## Estado em produção (conferido em 09/11/2026)

- **Calendários:** `24x7` e `comercial` (08–20, `America/Sao_Paulo`) cadastrados.
- **Escalonamento:** 4 passos no contrato padrão (1), `soc` → `noc` → `operator` → `admin`, todos ativos.
- **Pendentes, não cadastrados:** revisor e dia da amostra semanal, feriados, pausa de SLA no GLPI, fechamento automático (valor do GLPI não verificado) e fonte de escala de plantão real. Sem resposta, nenhum vai a produção como valor definitivo.

## Aceite

Em 09/11/2026 o Ricardo aceitou os 7 itens ("sim para todos"), como padrão interno, `contractual=false`, editável depois por contrato. O aceite não é promoção: o item 5 mexe em configuração do GLPI e só se aplica com frase própria; os itens 1, 4 e 7 ainda não têm campo cadastrado no banco.
