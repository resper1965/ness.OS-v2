# Investigação de casos L2 — plano de entregas

> Data: 11/11/2026. Depende do [ADR 0022](../../adr/0022-vigil-l2-investigation.md) (proposto) e da
> [avaliação do Vigil](../../evaluations/vigil-agentic-soc-assessment.md).
> Nada aqui autoriza instalação, compra, ingestão ou ativação em produção.

## Objetivo

Dar ao analista SOC uma investigação pronta nos casos graves (`TRIAGE_L2`), sem trocar o que já funciona
e sem criar uma segunda plataforma.

## Como fica, em uma linha

Wazuh → Hub (motor de risco, classificação, caso) → **só os L2** vão para a investigação → o resultado
volta para o caso no Hub → o analista decide.

O Hub não muda de papel. A investigação é uma etapa a mais, opcional, que pode falhar sem parar nada.

## Entregas

Cada entrega vale sozinha, tem um critério de pronto e um gate. Nenhuma começa antes do gate da anterior.

### E0 — Decisão registrada (agora, só documentos)

- Avaliação, ADR 0022 proposto e este plano no repositório.
- **Pronto quando:** os três arquivos estão na `main` e o índice de ADRs e o plano master apontam para eles.
- **Não mexe** no cutover do Zabbix de 14/11.

### E1 — Divergência e registro da decisão (F6, não depende do Vigil)

Duas mudanças pequenas no `/secops/triage`, úteis com ou sem Vigil:

- **Divergência:** quando o motor manda para L2 e o modelo devolve `FP` ou `LOW`, ou o motor dá L1 e o modelo devolve `HIGH` ou `CRIT`, a decisão é marcada. É **anotação, não roteamento**: o atendimento já é decidido antes do modelo (`_attendance_required`) e não muda. As decisões marcadas entram numa lista de revisão, no mesmo molde da amostra semanal de arquivados, e servem para calibrar limiares e prompt. Quando o motor arquiva, o modelo não roda, então não há divergência nesse sentido.
- **Registro:** a decisão guarda, além do que já guarda, a pontuação do motor com os motivos, o modelo usado e a resposta do modelo. Hoje isso só existe em linha de log.
- **Pronto quando:** teste cobre os dois sentidos da divergência e confirma que o atendimento não muda; uma decisão salva permite ver o que o modelo recebeu e respondeu; migração aplicada com rollback.
- **Gate:** revisão e promoção normais do Hub.

### E2 — Laboratório do Vigil (depois do primeiro gate da F7)

- Uma instância descartável, isolada, com tag de release e digest fixos.
- Só dado sintético ou do tenant interno `ness`. Sem integração de resposta. Sem acesso direto a Wazuh, Zabbix ou GLPI.
- Responde aos 7 itens de homologação do ADR 0022.
- Compara com a linha de base em uma amostra de casos L2: um analista lê as duas saídas sem saber a origem.
- **Pronto quando:** existe uma evidência datada em `docs/execution/evidence/` com a resposta de cada item e os números medidos (custo e tempo por caso, CPU, memória, disco).
- **Gate:** decisão do Ricardo. O ADR 0022 vira "aceita" ou "recusada".

Limites que precisam estar definidos **antes** do laboratório, para o resultado não ser discutido depois:

| Limite | Quem define | Proposta inicial |
|---|---|---|
| Tamanho da amostra | SOC | 30 casos L2 |
| Vigil ganha se | SOC | O analista preferir a saída dele em pelo menos 20 dos 30 |
| Custo máximo por caso | Ricardo | A definir |
| Tempo máximo por caso | SOC | A definir |

### E3 — Canário interno (só se o E2 passar)

- Vínculo decisão → caso: hoje a triagem grava a `SocDecision` sem `incident_id` e nada preenche esse campo depois. Antes do adaptador, o Hub precisa criar ou vincular o caso do L2 e expor esse vínculo.
- Adaptador no Hub: envia o pacote de evidência de um caso L2 e lê o resultado. Um arquivo de integração, no padrão dos outros.
- Onde guardar o resultado: uma tabela ou coluna própria, ligada à decisão, com o que foi enviado, o que voltou, modelo e custo. Mais a leitura disso na API do caso e na tela.
- Só o tenant `ness`. A investigação aparece no caso, marcada como gerada por IA, com as evidências citadas.
- Teto diário de investigações e teto de gasto na chave. Estourou, o caso segue sem investigação e a falha aparece no `pipeline_health`.
- **Pronto quando:** duas semanas de uso interno com a evidência registrada: quantos casos, quantas falhas, custo real, e a opinião dos analistas.
- **Gate:** aceite de jornada (F7) e decisão de capacidade para produção.

### E4 — Clientes, por onda

- Um cliente por vez, na ordem das faixas da F7. Cada cliente exige aceite próprio e conferência de contrato e LGPD para o envio de dados ao modelo.
- O teto diário é por tenant.
- **Pronto quando:** cada onda tem evidência e rollback (desligar a etapa para aquele tenant).
- **Gate:** o da faixa da F7 correspondente.

## Como escala

- Só os L2 chegam à investigação. O limiar de pontuação por contrato já controla esse volume.
- O teto diário por tenant controla o gasto.
- Crescer é liberar mais um tenant. Não exige mudar a arquitetura.

## Critérios de corte

O Vigil sai do plano, sem nova discussão, se no E2:

1. não houver como garantir isolamento entre tenants;
2. não houver como criar o caso e ler o resultado sem o daemon de polling;
3. algum componente do pacote não passar no ADR 0010 e não tiver substituto;
4. ele não ganhar da linha de base ou passar do custo máximo.

Se sair, a alternativa é dar ao próprio `soc_agent` duas ou três consultas de leitura para o caso L2. É
menos capaz, mas não cria outra pilha para operar.

## Fora de escopo

- Resposta automática de qualquer tipo.
- Vigil como console, como entrada de eventos ou como fonte de regras de detecção.
- LogLM e produtos pagos da DeepTempo.
- Tines, Shuffle, AiSOC e AlertSage como ferramentas (ver avaliação).

## Dependências humanas

- Ricardo: decisão do ADR 0022, custo máximo por caso, máquina do laboratório e de produção.
- SOC: amostra de casos, leitura comparativa, tempo máximo por caso.
