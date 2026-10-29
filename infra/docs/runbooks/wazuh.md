# Runbook Wazuh

## Silenciar ruído do Windows (regras locais 100100 = evento 5038, 100101 = driver Brother BrLog)

Motivo e medição: `docs/procurement/wazuh-bom-2026-10.md`. As regras ficam em `infra/wazuh/local_rules_noise.xml` (Wazuh 4.14, ids locais 100000+).

O repositório guarda só o bloco `<group>` das duas regras. Não guarda o `local_rules.xml` da instalação, backups, eventos de teste nem credenciais. Roda como root no manager; o host é o do inventário, não vai neste documento.

Escopo: a 100100 só pega `eventID` 5038 sob a 60104 (falha de auditoria); 4625/4624/4720 não passam por ela. A 100101 só pega `providerName` "Brother BrLog" sob a 60602; os demais erros de aplicação continuam na 60602 (nível 9) e na 61061 (nível 10).

1. Backup: `cp -a /var/ossec/etc/rules/local_rules.xml /var/ossec/etc/rules/local_rules.xml.bak-$(date +%Y%m%d)`
2. Acrescentar o `<group>` de `infra/wazuh/local_rules_noise.xml` ao fim de `/var/ossec/etc/rules/local_rules.xml`. Se o `local_rules.xml` já tiver `id="100100"` ou `id="100101"`, pare e revise: id duplicado derruba o analysisd.
3. Sintaxe, antes de reiniciar: `/var/ossec/bin/wazuh-analysisd -t && echo SINTAXE_OK`. Sem `SINTAXE_OK`, restaure o backup e não reinicie.
4. Teste sem reiniciar (o `wazuh-logtest` lê as regras do disco), com eventos sintéticos de EventChannel: `/var/ossec/bin/wazuh-logtest -l EventChannel < evento.json`
   - eventID `5038` em AUDIT_FAILURE: `rule id 100100 level 0`;
   - eventID `4625` em AUDIT_FAILURE: regra final **60122** (a 60105 é só intermediária), nunca 100100;
   - Application/ERROR com `providerName` "Brother BrLog": `rule id 100101 level 0`; com outro provedor: continua `60602`.
5. Reiniciar: `systemctl restart wazuh-manager` (agentes reconectam sozinhos, ~1 min sem análise).
6. Conferir após o restart, por hora, em `/var/ossec/logs/alerts/alerts.json`: `jq -r 'select(.data.win.system.eventID=="5038" or .data.win.system.providerName=="Brother BrLog") | .timestamp[0:13]' /var/ossec/logs/alerts/alerts.json | sort | uniq -c`. As horas posteriores ao restart devem ter 0 ocorrências; as anteriores mostram o volume que havia. Confirme também que 60122 e 60602 (outros provedores) continuam aparecendo.

Rollback: restaurar o `.bak` do passo 1, rodar `wazuh-analysisd -t` e reiniciar o manager.
