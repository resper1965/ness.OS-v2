# Política de atendimento SOC — proposta (03/11/2026)

**Estado:** proposta. Substitui o piso provisório `NINF_SOC_ATTENDANCE_MIN_LEVEL=12` quando o Ricardo aprovar.
Atendimento independe do score e do modelo de IA ([contrato de sinal v0](signal-contract-v0.md), regra 3).

| # | Regra |
|---|---|
| 1 | Nível Wazuh ≥ 12: atender sempre, com ticket. É o comportamento de hoje. |
| 2 | Níveis 7 a 11: o score decide, como hoje. Arquivado tem amostragem semanal, para "arquivado" não virar "ninguém viu". |
| 3 | Nível ≤ 6: arquivar guardando o evento bruto, sem ticket. |
| 4 | Regras próprias da NESS (`100100`, `100101`): atender sempre, qualquer nível. |
| 5 | Sem cliente ou cliente ambíguo: revisão técnica, sem enriquecimento externo nem IA, nunca no tenant `default`. |
| 6 | OT: análise retrospectiva por lote, com intervalo de até 24 h entre janelas. |
| 7 | Severidade ausente ou inválida: atender (já vale). Falha da IA não bloqueia o despacho (já vale). |

## Aberto

- Prazos de resposta por nível: dependem do SLA contratual (T08).
- OT: duração da janela, banda, capacidade e retenção.
- A regra 2 (amostragem semanal) e a regra 3 ainda não existem no código; entram na aprovação.
- A regra 4 hoje só vale se o nível da regra própria for ≥ 12 ou o score pedir atendimento.
