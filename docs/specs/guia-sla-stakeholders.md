# Guia de SLA para stakeholders

> Documento de apoio à conversa comercial e à implantação. Descreve **como o atendimento é medido** no
> ness.OS, **o que já está em operação** e **o que ainda está em implantação**. Nenhum prazo deste guia
> é uma promessa: os valores valem por contrato, e o que aparece marcado como *padrão interno* é o que
> a operação usa enquanto o contrato não define outra coisa.
>
> Versão de 11/11/2026, conferida contra `docs/specs/contratos-sla-editaveis.md` e o código da `main`.

## 0. Leia antes de apresentar

O ness.OS **guarda** a política de prazo por cliente e por severidade e **registra** cada passo do caso
com hora e autor. O **cálculo automático do prazo consumido**, o relatório de SLA, o escalonamento
automático e o fechamento automático ainda estão em implantação. Ao falar com o cliente, use a coluna
da direita da tabela abaixo.

| Já funciona hoje | Em implantação |
|---|---|
| Contrato com janela de atendimento, calendário e severidade por cliente | Cálculo do prazo consumido a partir do contrato |
| Guardar TTO e TTR contratados por severidade | Ler esses prazos automaticamente no atendimento (SLM do GLPI) |
| Caso com linha do tempo: alerta, ticket, responsável, solução | Escalonamento automático em 50/80/100 % |
| Cobertura por cliente: agentes, hosts, lacuna de sinal | Relatório de SLA por período com casos estourados |
| Contestação de severidade registrada com autor e motivo | Fechamento automático de caso solucionado |

## 1. Em uma frase

O atendimento é organizado por **severidade e contrato**: cada cliente tem uma janela de atendimento e
prazos de resposta e solução, e cada caso guarda o que aconteceu, quando e por quem. O que o cliente
compra é **tempo de resposta e de solução por severidade**; o resto é consequência disso.

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

TTO e TTR são **prazos do contrato**, guardados por severidade. Hoje eles são o número acordado e o
acompanhamento é feito pelo caso e pelo ticket; o cálculo automático do tempo consumido entra com o
SLM do GLPI.

O relógio corre no **calendário do contrato**: fora da janela de atendimento ele pausa. Um alerta às
19:00 de sexta com calendário comercial (08:00–20:00) só volta a correr às 08:00 de segunda.

## 4. Severidade: o que muda no atendimento

| Severidade | Exemplo | Janela | O que o cliente espera |
|---|---|---|---|
| 5 — Desastre | Serviço crítico parado, indisponibilidade ampla | 24×7 | Alguém olhando agora |
| 4 — Alta | Degradação relevante, disco cheio, interface principal caída | 24×7 | Resposta rápida, mesmo fora do horário |
| 3 — Média | Falha isolada, serviço secundário | Calendário | Atendimento na janela |
| 2 — Baixa | Evento sem impacto imediato | Calendário | Tratado na fila |
| 1 — Informativa | Ruído operacional | Calendário | Registro e acompanhamento |

A severidade **não é escolhida pelo cliente no momento do alerta**: ela vem da regra de correlação e do
contrato. O cliente pode contestar, e a contestação fica registrada com autor e motivo.

24×7 nas severidades 4 e 5 e janela comercial (08:00–20:00, `America/Sao_Paulo`) para o resto são o
**padrão interno** hoje. Em contrato, isso é uma linha negociada.

## 5. Escalonamento

O caminho de plantão é `soc` → `noc` → `operator` → `admin`, e os degraus são 50 %, 80 % e 100 % do
prazo. **Os degraus estão cadastrados na política, mas o disparo automático ainda não está ativo**: hoje
o caso sobe quando alguém percebe ou quando o prazo estoura. Ao apresentar, trate isso como o desenho
acordado, não como algo que já dispara sozinho.

O caminho de plantão é um **padrão interno**, porque depende de escala real, que ainda será definida. O
que é contratual é o prazo; quem resolve internamente não é.

## 6. Pausa e fechamento

- **Pausa do SLA:** o relógio só para quando o caso está **aguardando o cliente** (pendente de
  informação ou de acesso) e com motivo registrado. Tempo parado por falta de resposta do cliente não
  entra na conta do ness. A pausa depende de um campo do GLPI que **ainda não está configurado**.
- **Fechamento automático:** caso solucionado passar a fechado depois de 7 dias é o desenho acordado,
  **não está ativo**, e o valor hoje configurado no GLPI não foi verificado. Não apresente como
  funcionamento atual.

## 7. O que o cliente vê

- **Fila e caso:** cada caso mostra o alerta de origem, o ticket, o responsável e a linha do tempo com
  hora e autor de cada passo.
- **Cobertura:** quanto do parque está realmente monitorado, por cliente. Lacuna de coleta é mostrada,
  não escondida: um host sem agente não gera alerta, e é melhor o cliente ver isso do que descobrir
  depois.
- **Relatório de SLA por período:** **em implantação**. Até estar pronto, o acompanhamento é feito pela
  linha do tempo do caso.

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
- **Não cobre o que não é monitorado.** Host sem agente não gera alerta, e por isso a cobertura é parte
  do acordo.
- **Não cobre mudança planejada** feita pelo cliente ou por terceiro.
- **Não cobre resposta automática.** Remediação sempre tem aprovação humana.

## 10. Perguntas que vão aparecer

**"O prazo conta de madrugada?"** Depende do contrato. Hoje, severidade 4 e 5 contam 24×7; as demais
param fora de 08:00–20:00.

**"Se eu não responder, o prazo corre?"** Não, quando a pendência está registrada no caso. É por isso
que a pendência precisa ser dita no caso, não por telefone.

**"Como vocês provam o tempo de resposta?"** Pela linha do tempo do caso, que registra cada passo com
hora e autor. O relatório consolidado está em implantação.

**"E se o alerta não chegou?"** Aí é lacuna de cobertura, não SLA. O relatório de cobertura mostra, por
cliente, o que está sem sinal.

**"Posso mudar a severidade de um alerta?"** Pode contestar. A mudança fica registrada com autor e
motivo, para calibrar a regra depois.

## 11. Onde isso vive no produto

- Contratos, calendários e escalonamento são **campos editáveis por cliente**, sem código novo.
- O caso e o atendimento ficam no Hub; o registro do atendimento é o ticket no GLPI.
- Mudanças em contrato **ativo** ficam versionadas, com autor, data e o antes/depois. Contrato em
  rascunho (em negociação) ainda não gera essa trilha: feche o contrato antes de tratar o valor como
  acordado.

> Pendências conhecidas: cálculo automático de prazo e relatório de SLA, escalonamento automático,
> fechamento automático (valor do GLPI não verificado), pausa de SLA no GLPI, feriados e escala de
> plantão real. Enquanto isso, valem os padrões internos deste guia e o acompanhamento é manual.
