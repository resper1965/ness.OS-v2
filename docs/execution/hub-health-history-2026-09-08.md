# Histórico do monitor do hub — 08/09/2026

Implantado em produção às 22:25 UTC. Complementa a verificação de falhas descrita
em `hub-health-failure-verification-2026-09-08.md`.

## Comportamento

`hub-integration-monitor.sh` executa o probe com limite de 35 segundos dentro do
container, mais dois segundos para encerramento forçado do processo de diagnóstico.
O cliente Docker tem um limite externo de 40 segundos. Isso deixa margem para
publicar a falha antes do limite systemd de 55 segundos. Somente o processo do
probe recebe esse limite; API, workers e serviços monitorados não são encerrados.

`hub-health-history.py` valida o JSON, o estado dos componentes, duração finita e
não negativa, consistência do resultado e atualidade da verificação (até 120 s).
Saída vazia, traceback, resultado antigo ou sucesso com código de execução não
zero gera `status=error`, `detail=MonitorExecutionFailed`. O texto bruto de saída
inválida não é publicado. A troca de `status.json` é atômica.

Cada execução é acrescentada a `health-AAAA-MM-DD.jsonl` no diretório
`/var/lib/ness-os/hub-integration`, com arquivos 0600 e diretório 0700. São mantidos
o dia atual e os últimos 30 dias; a limpeza só remove arquivos com o nome e a data
previstos. A exclusão mútua evita duas execuções concorrentes do monitor.

## Consulta

No servidor do hub:

```bash
python3 /usr/local/sbin/ness-hub-health-history --summary --hours 24
```

O resumo fornece quantidade e período das amostras, amostras não saudáveis,
porcentagem de amostras não saudáveis e p50/p95 da duração dos probes. Sem dados,
os percentis e a porcentagem são nulos. Lacunas não são convertidas em sucesso.
Esses números não equivalem a disponibilidade temporal, SLA, taxa de erros de
requisições ou latência de entrega dos incidentes.

## Verificação

- Seis testes locais aprovados: dados válidos, saída vazia/traceback/código
  incompatível, dado antigo, números inválidos/estado inconsistente, retenção e
  permissões, cálculo de resumo e ausência de dados.
- Sintaxe Bash e formatação Python aprovadas.
- CLI executada no servidor com saída vazia e código 124: publicou erro e retornou
  código 1. Esse teste usou diretório separado do histórico operacional.
- Primeira amostra real: 22:25:18 UTC, todos os componentes ok, duas respostas de
  workers, filas vazias, nenhum retry/falha ou entrega pendente.
- Primeira execução automática após a implantação: amostra às 22:26:16 UTC,
  serviço encerrado com Result=success/ExecMainStatus=0; histórico com duas amostras
  válidas. Os percentis iniciais ainda não representam uma janela operacional longa.
- Workflow Backend CI atualizado para rodar os testes do histórico e validar o
  shell; YAML validado localmente. Execução no GitHub ainda não realizada.

Evidências e backup anterior em `/opt/n-infraops/rollback/health-20260908/`:
`monitor.before.sh`, `monitor-failure-example.json`, `history-summary-initial.json`
e cópias dos novos scripts.

Reversão: restaurar `monitor.before.sh` em
`/usr/local/sbin/ness-hub-integration-monitor`. Preservar os arquivos de histórico;
não há necessidade de apagar dados para reverter o executor.

O histórico começou nesta implantação. Não há prova antecipada de D+1/D+3/D+7 nem
de cobertura completa dos healthchecks dos outros sistemas.
