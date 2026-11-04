# P2: proposta de valores para decisão (04/11/2026)

**Estado:** proposta do agente. Nada aqui está decidido nem implementado. Cada linha espera aceite ou correção do Ricardo; os prazos de resposta ainda dependem do SLA contratual (T08).

## 1. Prazos de resposta por nível Wazuh

| Nível | Resposta (primeiro contato) | Observação |
|---|---|---|
| ≥ 12 | 15 min, 24x7 | atende sempre, com ticket (regra 1) |
| 7 a 11, atendido pelo score | 4 h, horário comercial | |
| ≤ 6 com score ≥ 75 | 1 h, 24x7 | IOC confirmado ou ativo crítico (regra 3) |
| Sem cliente ou ambíguo | 1 dia útil | revisão técnica (regra 5) |

Fator decisivo: o contrato de cada cliente prevalece. Estes valores só valem como padrão onde o contrato é omisso.

## 2. Sonda OT

| Item | Proposta | Por quê |
|---|---|---|
| Janela | 24 h, fechada às 00:00 UTC | já aprovada como teto (regra 6) |
| Banda | sem limite no protocolo; lote de até 50 MB compactado | OT costuma ter enlace estreito; lote grande vira reenvio |
| Retenção do lote bruto | 90 dias | cobre uma auditoria trimestral |
| Retenção do resultado da análise | 13 meses | cobre a comparação anual |
| Capacidade | 1 sonda por site, dimensionada no piloto (P4) | só se mede com cliente real |

Fator decisivo: retenção de evidência cria custo de armazenamento permanente. Prefira o menor prazo que atende ao contrato.

## 3. Revisão da amostra semanal de arquivados

| Item | Proposta |
|---|---|
| Quem | analista de plantão do SOC, em rodízio semanal |
| Quando | segunda-feira, até as 12:00 |
| Tamanho | 20 alertas por semana por cliente com volume; todos se houver menos de 20 |
| Registro | resultado no próprio ticket de revisão, sem planilha à parte |
| Escalonamento | um arquivado que devia ter sido atendido abre ajuste de regra, sem alterar o piso 12 |

## Como aceitar

Responda com a linha e a palavra "aceito", ou com o valor corrigido. O que for aceito vira regra em `soc-attendance-policy.md` e `signal-contract-v1.md` no mesmo PR.
