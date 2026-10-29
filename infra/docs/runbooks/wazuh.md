# Runbook Wazuh

## Silenciar ruido do Windows (regras locais 100100 = evento 5038, 100101 = driver Brother BrLog)

Motivo e medição: `docs/procurement/wazuh-bom-2026-10.md`. A regra fica em `infra/wazuh/local_rules_noise.xml`. Roda como root no manager (Hostinger `62.72.8.164` até a migração).

1. Backup: `cp -a /var/ossec/etc/rules/local_rules.xml /var/ossec/etc/rules/local_rules.xml.bak-$(date +%Y%m%d)`
2. Acrescentar o conteudo de `infra/wazuh/local_rules_noise.xml` (so o `<group>`) ao fim do arquivo (o repositório não guarda o `local_rules.xml` inteiro, que é da instalação).
3. Testar sem reiniciar: `/var/ossec/bin/wazuh-logtest -l EventChannel < evento.json`, com um evento `5038` sintético; esperado `rule id 100100 level 0`, e um evento `4625` ainda em `60105`.
4. Reiniciar: `systemctl restart wazuh-manager` (agentes reconectam sozinhos, ~1 min sem análise).
5. Sintaxe antes de reiniciar: `/var/ossec/bin/wazuh-analysisd -t && echo SINTAXE_OK`.
6. Conferir após 10 min: `grep -c '"id":"60104"'` nos últimos alertas deve cair para ~1% do que era.

Rollback: restaurar o `.bak` do passo 1 e reiniciar.
