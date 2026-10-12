# ness.os — fluxo isolado Zabbix, Hub e GLPI

Data: 12/10/2026 BRT. Runner: VPS AIOps, containers descartáveis limitados a
1 CPU/1 GiB (PostgreSQL e teste), 0,5 CPU/128 MiB (Redis). Rede Docker interna,
nenhuma porta publicada, nenhum segredo ou volume produtivo montado.

O runner usa `infra/tests/run-hub-isolated-flow.sh`; fonte do teste em
`app/backend/tests/test_hub_local_flow.py`, commit `f18af10`. Dependências da
imagem API imutável `sha256:cd3224cfa5a361f5bf24d9f2c02bcfcb5af2e784e8c8dd4d1c3a64b77a1caadf`.
PostgreSQL/Redis reais e novos; APIs Zabbix/GLPI simuladas por MockTransport.

Resultado: **1 passed**, 3,75 segundos na rodada de três replays.

Provas cobertas:
- GLPI cria ticket, mas a resposta se perde; incidente persiste sem vínculo.
- Retry encontra o ticket existente e reaproveita seu ID.
- Três replays preservam um incidente e uma criação de ticket.
- Auditoria registra criação, falha e reaproveitamento.
- Viewer consulta seu tenant e recebe 403 ao solicitar outro.
- Recovery marca a origem resolvida e preserva vínculo; incidente continua
  aberto conforme comportamento atual. Encerramento GLPI não está comprovado.
- Conteúdo do alerta é escapado antes do envio ao ticket.

Containers e rede temporários foram removidos pelo trap, com ausência
confirmada após a rodada final; API e workers produtivos permaneceram healthy.
O diretório root-only de código em
`/var/tmp/ness-isolated-flow-20261012` contém apenas arquivo Git, sem segredos,
e pode ser reutilizado para os próximos ensaios.

Esta prova desbloqueia desenvolvimento independente do Docker Desktop local,
mas não aprova G2, escrita GLPI produtiva, corte Zabbix ou aceite MVP.
