# Reativação da origem Zabbix — 02/09/2026

## Causa da indisponibilidade operacional

Depois do rollback de DNS para `144.91.72.202`, o frontend estava disponível,
mas o motor `zabbix-server` permanecia `inactive/masked`. A porta 10051 era
ocupada por `ness-zabbix-cutover-bridge`, que encaminhava conexões para
`169.58.234.9:10051`; o destino não aceitava conexões.

Assim, o teste anterior de abertura da porta validava somente o `socat`, não o
processo de coleta.

## Reativação

Com autorização operacional explícita:

- a configuração passou em `zabbix_server -T` antes da mudança;
- o bridge foi parado e desabilitado;
- `zabbix-server` foi desmascarado, habilitado e iniciado;
- a porta 10051 passou a pertencer ao processo `zabbix_server`;
- os 18 de 18 proxies voltaram a registrar acesso nos últimos cinco minutos;
- MariaDB e Apache permaneceram ativos.

Evidência final root-only:
`/var/lib/ness-os/restore-evidence/source-reactivation-final-20260902T155332-0300`.

A primeira tentativa foi revertida automaticamente por um critério de
verificação excessivo sobre processos `socat`. A evidência correspondente foi
marcada `INVALIDATED`; a segunda tentativa revertida foi marcada
`ROLLED_BACK`. Nenhuma delas deve ser usada como comprovação final.

## Contenção de notificações

Logo após a reativação, o Zabbix produziu 42.992 notificações com status
`FAILED`; nenhuma ficou pendente ou foi enviada. As causas agregadas foram:

- 39.424: `No media defined for user`;
- 2.877: `No message defined for media type`;
- 691: `Media type disabled`.

Para interromper novas tentativas inválidas sem desligar a coleta, a API do
Zabbix desabilitou temporariamente as cinco ações ativas e o único tipo de
mídia ativo. O histórico foi preservado e não houve exclusão de alertas.

Evidência root-only:
`/var/lib/ness-os/restore-evidence/notification-containment-20260902T155519-0300`.

Antes de reativar notificações, é necessário corrigir os vínculos de mídia dos
usuários e definir mensagens para o tipo de mídia, seguido de teste controlado.

## Verificação após estabilização

- `zabbix-server=active/enabled` e bridge `inactive/disabled`;
- 18 de 18 proxies com acesso nos últimos cinco minutos;
- nenhuma notificação nova pendente após a contenção;
- 20 de 20 requisições externas ao frontend com HTTP 200, mediana de 725,8 ms
  e p95 de 817,7 ms;
- API pública em `7.0.27` e TCP/10051 acessível externamente;
- início do SAML em HTTP 302 para o endpoint correto, com `SAMLRequest`.

O ambiente possui somente dois usuários com mídia habilitada. Embora existam
cinco templates no tipo de mídia `1`, as ações atingem usuários sem mídia e há
combinações de evento/operação sem mensagem compatível. Esses destinatários não
devem ser inventados; as notificações permanecem contidas até a reconciliação
controlada dos responsáveis e dos templates.

## Frescor da coleta observado na interface

A captura do dashboard feita às 15:50 ainda refletia o período anterior à
reativação das 15:52. Depois da reativação, os itens internos passaram a gravar
valores entre 15:57 e 15:59 (horário de São Paulo), incluindo disponibilidade,
filas, processos e throughput. Os 18 proxies também atualizaram nesse período.

A fila total passou de 6.267 para 6.225 itens entre duas leituras consecutivas;
5.859 estavam atrasados há mais de dez minutos. A coleta está ativa e a fila de
recuperação está escoando, mas alguns widgets podem permanecer incompletos até
o backlog estabilizar. Datas antigas na tabela **Current problems** representam
o início do problema, não necessariamente a última coleta do item.
