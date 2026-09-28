# Recuperação Zabbix no Hub

O campo `event_id` do webhook identifica o **evento de problema original** tanto em `PROBLEM` quanto em `RESOLVED`/`OK`. Na operação de recuperação do Zabbix 7.0, configurar `{EVENT.ID}` para esse campo; `{EVENT.RECOVERY.ID}` é o identificador distinto do evento de recuperação. [Exemplo oficial de macros do Zabbix](https://www.zabbix.com/documentation/7.0/en/manual/config/notifications/action/operation/macros).

O Hub correlaciona pelo host, trigger e evento de problema. Na recuperação, registra `ninf_zabbix_status=resolved`, horário e ação `zabbix_recovered` uma vez. O ticket GLPI e o estado de atendimento do incidente permanecem até a solução no GLPI ou ação autorizada no Hub. Um replay não duplica a ação. Se a recuperação chegar antes da persistência do problema, o worker tenta novamente; se IDs não corresponderem, falha fechado. A recuperação nunca cria incidente ou ticket.

Esta política precisa ser validada no ensaio sintético ponta a ponta da Fase 2. Não altera o gate de produção da Fase 0.
