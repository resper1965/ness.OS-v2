# Padrões operacionais propostos

> Task 1 do [plano de aceleração](../superpowers/plans/2026-11-05-acelerar-producao.md).
> Todos são `contractual=false`, internos, editáveis depois pela tela de contratos.

| Item | Padrão proposto | Onde é editável | Se o Ricardo não responder em 24 h |
|---|---|---|---|
| Revisor da amostra semanal | Papel `soc` de plantão, segunda-feira 09:00 BRT | `n_infraops_contract_policy_params`, chave pendente | Segue com seed em ambiente de teste, **não** promove |
| Calendário padrão | 24×7 para severidade 4 e 5; 08–18 BRT dias úteis para o resto, feriados nacionais do ano | Calendários do contrato (`n_infraops_sla_calendars`) | idem |
| Escalonamento | 50/80/100 % do prazo, papéis padrão | `n_infraops_escalation_steps` | idem |
| Pausa do SLA | Só em status "Pendente" com motivo aprovado | Política do contrato (campo pendente no GLPI) | idem |
| Fechamento automático | Solucionado → Fechado em 7 dias, com reabertura | Configuração do GLPI (valor atual não verificado) | idem |
| Janela OT retrospectiva | 24 h (teto da política SOC) | `ot_retrospective_hours`, máx. 24 | idem |
| Plantão | Ordem atual por papel `soc` → `noc` → `operator` → `admin` até haver fonte de escala real | `n_infraops_escalation_steps` (contrato padrão) | idem |

## Pergunta ao Ricardo

> Aceita estes padrões internos, editáveis depois por contrato? (sim/não por linha)
