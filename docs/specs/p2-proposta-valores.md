# P2: proposta de valores para decisão (04/11/2026)

**Estado:** aceito pelo Ricardo em 04/11/2026, com as condições abaixo. As regras de prazo entram em `soc-attendance-policy.md`.

## 1. Prazos de resposta por nível Wazuh

| Nível | Resposta (primeiro contato) | Observação |
|---|---|---|
| ≥ 12 | 15 min, 24x7 | atende sempre, com ticket (regra 1) |
| 7 a 11, atendido pelo score | 4 h, horário comercial | |
| ≤ 6 com score ≥ 75 | 1 h, 24x7 | IOC confirmado ou ativo crítico (regra 3) |
| Severidade ausente ou inválida | 4 h, horário comercial | atende por regra (regra 7); sem nível, não se presume gravidade |
| Regra própria da NESS que detecta, abaixo do nível 12 | 4 h, horário comercial | atende sempre (regra 4); a regra de detecção ainda não existe no código |
| Sem cliente ou ambíguo | 1 dia útil | revisão técnica (regra 5) |

Fator decisivo: o contrato de cada cliente prevalece. Estes valores só valem como padrão onde o contrato é omisso.

## 2. Sonda OT

**Fora desta proposta.** Ainda não há projeto operacional de OT, então janela, banda, retenção e capacidade não têm cliente nem contrato para dimensionar. A janela de até 24 h (regra 6) continua como teto aprovado. Os demais valores são decididos no piloto do P4, com cliente real.

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
