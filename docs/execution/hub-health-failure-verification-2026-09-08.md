# Verificação de saúde e falhas do hub — 08/09/2026

Estado: correção aplicada e verificada em produção, 22:21–22:22 UTC.

## Problemas corrigidos

O endpoint do painel substituía qualquer detalhe do GLPI por uma mensagem de
leitura autenticada, inclusive quando o status era erro. Agora preserva o erro e
só informa leitura verificada quando o probe efetivamente retorna sucesso.

O agregador aceitava qualquer retorno sem exceção como saudável. Agora exige
`status=ready` dos probes autenticados e estados conhecidos das verificações de
consumidores/entregas; respostas ausentes ou inválidas resultam em erro.

Cada verificação possui deadline assíncrono de 20 segundos e duração medida por
relógio monotônico (`duration_ms`). O GLPI tenta encerrar a sessão também quando
a leitura é cancelada, com até cinco segundos adicionais para limpeza. A conexão
e as operações Redis do monitor têm timeout de quatro segundos. O serviço systemd
mantém seu limite externo de 55 segundos. Os deadlines dependem do cancelamento
cooperativo das operações assíncronas; não equivalem a um deadline rígido de
processo nem medem a latência de entrega ponta a ponta dos incidentes.

## Provas

- 235 testes do backend aprovados, incluindo nove novos casos de regressão.
- MyPy aprovado para 76 arquivos; Ruff aprovado nos arquivos alterados.
- Testes de resposta inválida, timeout, cancelamento, erro sem exposição da
  mensagem original da exceção, fila degradada e falha de banco.
- Sessão GLPI encerrada durante cancelamento, preservando a propagação do cancelamento.
- Aplicação no hub após comparação do diff com os arquivos efetivamente instalados.

O script `infra/scripts/hub-pipeline-failure-check.py` foi executado dentro do
container da API. Seus overrides valem apenas para aquele processo; não alteram
configuração persistente nem param GLPI, Redis ou workers. Foram usados endereço
local com conexão recusada e credenciais fictícias na chamada negativa do GLPI.

| Caso | Resultado observado |
| --- | --- |
| Dependências reais | ok; total 3298,9 ms; Zabbix 526,3 ms; GLPI 526,5 ms |
| Conexão GLPI recusada | fluxo degraded; GLPI error/RuntimeError; detalhe preservado no retorno do painel |
| Conexão Redis recusada | fluxo degraded; workers error/ConnectionError; GLPI permaneceu ok |
| Deadline reduzido no processo de teste | error/TimeoutError; 21,2 ms |

O monitor normal após a publicação também registrou Zabbix, GLPI, consumidores e
entregas em estado ok; duas respostas de workers, filas vazias, nenhuma falha/retry,
nenhum incidente sem ticket acima de cinco minutos e nenhuma resolução pendente.

## Evidência e reversão

Diretório protegido no servidor: `/opt/n-infraops/rollback/health-20260908/`.
Contém os três arquivos anteriores (`*.before.py`), os três arquivos publicados,
`deployed-health.json`, `failure-check.jsonl` e o script de verificação.

Reversão: restaurar pipeline_health.before.py e glpi.before.py em
`/opt/n-infraops/app/backend/app/integrations/`, pipeline.before.py em
`/opt/n-infraops/app/backend/app/api/routers/pipeline.py`, reiniciar ninf-api e
executar o monitor. A mudança não altera schema, credenciais nem dados de clientes.

## Escopo ainda aberto

Esta entrega prova o comportamento do monitor do fluxo hub/GLPI. Não comprova
todos os healthchecks do ecossistema, distribuição histórica de latência/taxa de
erro, capacidade sob carga ou perda real prolongada de cada dependência. Esses
requisitos permanecem abertos na matriz F4/F5/F7.
