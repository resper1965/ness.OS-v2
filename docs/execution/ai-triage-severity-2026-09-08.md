# Triagem sem rebaixamento de severidade — 08/09/2026

Correção aplicada ao analisador de alertas v1 e publicada no worker de alertas.

## Problema e comportamento final

Antes, falta de chave, cota esgotada, timeout e resposta inválida do Gemini
retornavam urgência MEDIUM para qualquer evento. Assim, um evento Zabbix DISASTER
era apresentado como uma análise de urgência média quando o provedor falhava.

A triagem manual agora preserva o piso de prioridade derivado da origem:

| Severidade recebida | Urgência mínima |
| --- | --- |
| 1 / INFORMATION / LOW | LOW |
| 2 / WARNING; 3 / AVERAGE | MEDIUM |
| 4 / HIGH | HIGH |
| 5 / DISASTER / CRITICAL | CRITICAL |
| Ausente, não classificada ou desconhecida | MEDIUM, exigindo triagem manual |

Uma análise retornada pela IA pode elevar a urgência, mas não reduzi-la abaixo
desse piso. O contrato Pydantic aceita somente LOW, MEDIUM, HIGH e CRITICAL;
valor diferente faz a análise cair na triagem manual. O fallback não inventa
causa confirmada nem solicita isolamento: orienta validar impacto e causa antes
de executar ação corretiva.

## Evidências

- 249 testes do backend aprovados, incluindo combinações de severidade com cota,
  timeout e resposta inválida, ausência de chave sem chamada HTTP e tentativa de
  rebaixamento/urgência inválida retornada pelo modelo.
- MyPy aprovado em 76 arquivos; Ruff e formatação aprovados nos arquivos alterados.
- Diff comparado contra o analisador instalado antes da publicação.
- Worker de alertas encerrado por TERM e retomado normalmente, sem kill forçado
  nem remoção de mensagens da fila.
- Verificação no container do worker, em processo separado com chave vazia e
  cliente HTTP bloqueado: severidades 1/3/4/5/DISASTER resultaram em
  LOW/MEDIUM/HIGH/CRITICAL/CRITICAL, todas com triagem manual e sem isolamento.
  Nenhuma chamada Gemini foi necessária para essa prova.

Rollback e evidências em `/opt/n-infraops/rollback/analyzer-20260908/`:
`analyzer.before.py`, `analyzer.py`, `runtime-check.jsonl`, `health-after.json`.
Reversão: restaurar o arquivo anterior em
`/opt/n-infraops/app/backend/app/ml/analyzer.py` e recarregar o worker de alertas
com encerramento normal. Não há migração de dados.

## Limites do aceite

Esta entrega corrige a prioridade da triagem v1; não conclui F5. Permanecem
pendentes a classificação completa por domínio, aprovação humana auditável para
execução de runbooks e os demais caminhos de análise/post-mortem. A construção
atual do prompt ainda usa payload e metadados completos; a minimização de dados,
segredos e isolamento do contexto enviado ao provedor precisa de uma entrega
específica antes do aceite F5-6. O orçamento Gemini continua sem definição.
