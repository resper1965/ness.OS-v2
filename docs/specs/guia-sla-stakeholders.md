# Guia de SLA para stakeholders

> Documento de apoio à conversa comercial e à implantação. Descreve **como o atendimento é medido** no
> ness.OS e **o que cada cliente precisa decidir no contrato**. Nenhum prazo deste guia é uma promessa:
> os valores valem por contrato, e o que aparece marcado como *padrão interno* é o que a operação usa
> enquanto o contrato não define outra coisa.
>
> Versão de 11/11/2026. Fonte dos números de operação: `docs/specs/contratos-sla-editaveis.md`.

## 1. Em uma frase

O ness.OS mede o tempo do alerta até a solução, por cliente e por severidade, com calendário e prazos
que vêm do contrato. O que o cliente compra é um **tempo de resposta e de solução por severidade**; o
resto é consequência disso.

## 2. Contratual e interno: a distinção que precisa ficar clara

| | Contratual | Padrão interno |
|---|---|---|
| O que é | Prazo que o cliente pode cobrar | O que a operação usa por falta de definição no contrato |
| Quem define | Cliente e ness, no contrato | SOC, com aceite da direção |
| Onde fica | Tela de contratos do Hub, por cliente | Mesmo lugar, marcado `contractual = não` |
| Pode ser cobrado? | Sim | **Não** |

Regra de ouro: **nada é vendido nem cobrado sem estar no contrato.** O padrão interno existe para a
operação não parar, não para virar promessa.

## 3. Os quatro tempos que importam

1. **Detecção** — do evento acontecer até o alerta chegar ao Hub. Depende da coleta (Zabbix para
   disponibilidade, Wazuh para exposição). Não é prazo contratual; é o que a cobertura mede.
2. **Resposta (TTO)** — do alerta chegar até alguém assumir o caso.
3. **Solução (TTR)** — da abertura até a solução registrada.
4. **Fechamento** — da solução até o caso ser encerrado. É administrativo e não conta como demora.

O relógio de TTO e TTR corre no **calendário do contrato**: fora da janela de atendimento ele pausa.
Um alerta às 19:00 de sexta com calendário comercial (08:00–20:00) tem o relógio parado das 20:00 às
08:00 de segunda.

## 4. Severidade: o que muda no atendimento

| Severidade | Exemplo | Janela | O que o cliente espera |
|---|---|---|---|
| 5 — Desastre | Serviço crítico parado, indisponibilidade ampla | 24×7 | Alguém olhando agora |
| 4 — Alta | Degradação relevante, disco cheio, interface principal caída | 24×7 | Resposta rápida, mesmo fora do horário |
| 3 — Média | Falha isolada, serviço secundário | Calendário | Atendimento na janela |
| 2 — Baixa | Evento sem impacto imediato | Calendário | Tratado na fila |
| 1 — Informativa | Ruído operacional | Calendário | Registro e acompanhamento |

A severidade **não é escolhida pelo cliente no momento do alerta**: ela vem da regra de correlação e do
contrato. O cliente pode contestar, e a contestação fica registrada.

24×7 nas severidades 4 e 5 e janela comercial (08:00–20:00, `America/Sao_Paulo`) para o resto são o
**padrão interno** hoje. Em contrato, isso é uma linha negociada.

## 5. Escalonamento

Enquanto o prazo corre, o caso sobe de degrau:

- **50 % do prazo** — entra o segundo nível de plantão.
- **80 %** — entra a coordenação.
- **100 %** — o caso é marcado como estourado e entra na pauta do dia.

O caminho padrão de plantão é `soc` → `noc` → `operator` → `admin`. É um **padrão interno**, porque
depende de escala real, que ainda será definida. O que é contratual é o prazo; o caminho interno de
quem resolve não é.

## 6. Pausa e fechamento

- **Pausa do SLA:** o relógio só para quando o caso está **aguardando o cliente** (pendente de
  informação ou de acesso) e com motivo registrado. Tempo parado por falta de resposta do cliente não
  entra na conta do ness.
- **Fechamento automático:** caso solucionado passa a fechado depois de 7 dias, com direito a reabertura.
  Isso é padrão interno hoje; o valor do GLPI precisa ser conferido antes de virar contrato.

## 7. O que o cliente vê

- **Fila e caso:** cada caso mostra o prazo consumido, o responsável e a linha do tempo.
- **Cobertura:** quanto do parque está realmente monitorado, por cliente. Lacuna de coleta é mostrada,
  não escondida: um host sem agente não gera alerta, e é melhor o cliente ver isso do que descobrir
  depois.
- **Relatório:** consumo de SLA por período e por severidade, com os casos estourados nomeados.

## 8. O que precisa ser decidido no contrato

Esta é a lista que fecha o assunto com o cliente. Sem ela, a operação usa o padrão interno e o cliente
não pode cobrar.

| Campo | Descrição | Valor |
|---|---|---|
| Janela de atendimento | Dias e horários, com fuso | a definir |
| Feriados | Quais dias não contam | a definir |
| TTO por severidade | Prazo de resposta para 3, 4 e 5 | a definir |
| TTR por severidade | Prazo de solução para 3, 4 e 5 | a definir |
| Cobertura mínima | Percentual de hosts com coleta ativa | a definir |
| Plantão estendido | Se cobre 24×7 além de 4 e 5 | a definir |
| Exclusões | O que não conta como incidente | a definir |

## 9. O que este SLA não cobre

- **Não é disponibilidade garantida do serviço do cliente.** O ness.OS mede e atende; não substitui a
  arquitetura do cliente.
- **Não cobre o que não é monitorado.** Host sem agente não gera alerta, e por isso a cobertura é
  parte do acordo.
- **Não cobre mudança planejada** feita pelo cliente ou por terceiro.
- **Não cobre resposta automática.** Remediação sempre tem aprovação humana.

## 10. Perguntas que vão aparecer

**"O prazo conta de madrugada?"** Depende do contrato. Hoje, severidade 4 e 5 contam 24×7; as demais
param fora de 08:00–20:00.

**"Se eu não responder, o prazo corre?"** Não. Caso aguardando cliente pausa o relógio, com motivo
registrado. É por isso que a pendência precisa ser dita no caso, não por telefone.

**"Como vocês provam o tempo de resposta?"** Pela linha do tempo do caso e pelo relatório de SLA. Cada
passo é registrado com hora e autor.

**"E se o alerta não chegou?"** Aí é lacuna de cobertura, não SLA. O relatório de cobertura mostra, por
cliente, o que está sem sinal.

**"Posso mudar a severidade de um alerta?"** Pode contestar. A mudança fica registrada com autor e
motivo, para calibrar a regra depois.

## 11. Onde isso vive no produto

- Contratos, calendários e escalonamento são **campos editáveis por cliente**, sem código novo.
- O prazo consumido é calculado no Hub, não no GLPI: o GLPI é o registro do atendimento.
- Toda alteração de contrato fica versionada, com autor e data.

> Pendências conhecidas: feriados, escala de plantão real e o valor de fechamento automático do GLPI
> ainda não estão cadastrados. Enquanto isso, valem os padrões internos deste guia.
