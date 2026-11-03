# Política de atendimento SOC (03/11/2026)

**Estado:** aprovada pelo Ricardo em 03/11/2026 (regras 1 a 6). O piso `NINF_SOC_ATTENDANCE_MIN_LEVEL=12` deixa de ser provisório.
Atendimento independe do score e do modelo de IA ([contrato de sinal v0](signal-contract-v0.md), regra 3).

| # | Regra |
|---|---|
| 1 | Nível Wazuh ≥ 12: atender sempre, com ticket. É o comportamento de hoje. |
| 2 | Níveis 7 a 11: o score decide, como hoje. Arquivado tem amostragem semanal, para "arquivado" não virar "ninguém viu". |
| 3 | Nível ≤ 6: arquivar guardando o evento bruto, sem ticket. |
| 4 | Regras próprias da NESS que **detectam** algo: atender sempre, qualquer nível. As regras de silêncio (`100100`, `100101`, nível 0, só reduzem ruído do Windows 5038 e do driver Brother) ficam **fora**: nunca geram atendimento. Lista de IDs de detecção própria: a definir quando existir a primeira. |
| 5 | Sem cliente ou cliente ambíguo: revisão técnica, sem enriquecimento externo nem IA, nunca no tenant `default`. |
| 6 | OT: análise retrospectiva por lote, com intervalo de até 24 h entre janelas. |
| 7 | Severidade ausente ou inválida: atender (já vale). Falha da IA não bloqueia o despacho (já vale). |

## Aberto

- Prazos de resposta por nível: dependem do SLA contratual (T08).
- OT: duração da janela, banda, capacidade e retenção.
- Implementado: regras 1, 2, 3, 5 e 7 (`/api/secops/triage`; amostra semanal em `GET /api/secops/archived-sample`, que sorteia os arquivados da janela). O evento bruto fica em `raw_alert` da decisão.
- Regra 6 (OT) e a revisão semanal automatizada (quem olha a amostra, e quando) ainda não existem.
- A regra 4 hoje não existe no código e ainda não há regra própria de detecção cadastrada.
