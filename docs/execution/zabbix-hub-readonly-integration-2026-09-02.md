# Integração Zabbix → hub em leitura — 02/09/2026

## Resultado

O hub deixou de depender de um token pessoal e passou a consultar o Zabbix
7.0.27 com uma identidade técnica dedicada, sem acesso à interface e limitada
a oito métodos de leitura da API:

- `event.get`;
- `history.get`;
- `host.get`;
- `item.get`;
- `problem.get`;
- `proxy.get`;
- `trend.get`;
- `trigger.get`.

O usuário `svc_ninfraops_api` usa o papel e o grupo `n.infraops API Read Only`.
O grupo possui leitura dos 243 host groups existentes no momento da criação. O
token expira em 01/12/2026 00:00 BRT; a ampliação futura de host groups deve
reconciliar explicitamente os direitos desse grupo.

## Controles aplicados

Antes do provisionamento, o contador de IDs de `users_groups` estava uma
posição atrás da tabela. A inconsistência foi corrigida em transação pela
camada de banco do Zabbix, de `40` para o máximo vigente `41`, e todos os
contadores envolvidos foram comparados novamente. Nenhum objeto funcional foi
alterado nessa correção.

O provisionamento usou os serviços internos do Zabbix com auditoria e
transação. A prova positiva executou `apiinfo.version` e `host.get`; a prova
negativa confirmou que `token.get` é negado. Nenhuma escrita operacional foi
executada.

O segredo foi transmitido diretamente entre os dois servidores, nunca exibido
ou gravado no workspace. No hub, ele reside em
`/etc/ness-os/zabbix-integration.env`, com proprietário `root:root` e modo
`0600`. A cópia antiga em `.env` foi removida após backup restrito, mantendo
uma única fonte efetiva de configuração. Os arquivos temporários de transporte
foram eliminados nos dois hosts.

Após a prova do novo acesso, o token pessoal de cutover ID 4 foi desativado por
uma atualização auditada. O token anterior ID 3 já estava desativado. O token
técnico ID 5 permaneceu ativo e o readiness do hub continuou aprovado após a
revogação.

## Evidências e rollback

- correção do contador:
  `/var/lib/ness-os/restore-evidence/zabbix-id-reconcile-20260902T1915-0300`;
- criação e prova da identidade:
  `/var/lib/ness-os/restore-evidence/zabbix-hub-readonly-20260902T1920-0300-retry2`;
- desativação do token de cutover:
  `/var/lib/ness-os/restore-evidence/zabbix-cutover-token-retirement-20260902T1950-0300`;
- integração no hub e fontes anteriores:
  `/opt/n-infraops/rollback/zabbix-hub-readonly-20260902T1942-0300-retry1`.

O aceite registrou Zabbix autenticado em modo de leitura, versão 7.0.27, uma
amostra de host visível e zero escritas. O readiness privado do GLPI permaneceu
aprovado e `https://hub.ness.com.br/` respondeu HTTP 200. A integração conclui
o item de credencial e contrato Zabbix → hub da F4; correlação, idempotência e
o fluxo completo de incidente ainda permanecem no gate da onda.
