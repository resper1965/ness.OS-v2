# Wazuh: revisão de regras (29/10/2026)

Origem: Wazuh Hostinger (`homol`, 4.14.1), leitura por `ness_ro` (SSH) e `ness_ro_api` (papel `readonly`). Só o item "Aplicado" mudou produção.

## Aplicado em produção

| Regra | Efeito | Motivo medido |
|---|---|---|
| `100100` (filha da `60104`, nível 0) | silencia o evento Windows 5038 (integridade de código) | 66% de todos os alertas; 509 agentes, nenhum acima de 2% |
| `100101` (filha da `60602`, nível 0) | silencia o provedor `Brother BrLog` (driver de impressora) | 36% dos alertas restantes; quase toda a `61061` (nível 10) |

Resultado: o manager passou de 39% de alertas por evento recebido para cerca de 3%. Reinício do manager: ~1 min sem análise. Código e roteiro: `infra/wazuh/local_rules_noise.xml`, `infra/docs/runbooks/wazuh.md` (PR #120). Backups do `local_rules.xml` ficam no próprio host.

## Medido no conjunto (amostra de 138 mil alertas, sem o 5038)

- 4.512 regras ativas em 168 arquivos; 750 técnicas MITRE conhecidas; única regra local anterior: o exemplo `100001`.
- Logon/logoff (4624/4634): 24% do volume, nível 3. Base para detectar acesso remoto; não alertar.
- Boas: `92656` (RDP, nível 12, T1021.001) e `60154` (grupo Administradores alterado).
- FIM do registro (`750/751/752`): 12% do volume; a regra `241` mostra o limite de valores monitorados já atingido, ou seja, vigia chave demais.
- Os `agent.conf` dos grupos só têm o rótulo `cliente`. A coleta real vem do `ossec.conf` local de cada agente (não auditado).

## Lacunas de cobertura (0 ocorrências no dia)

Sysmon, criação de processo (4688), PowerShell script block (4104), limpeza de log (1102) e tarefa agendada (4698). Defender (716), PowerShell (152) e serviço novo (7045, 111) aparecem pouco. Pode ser coleta desligada ou ausência real do evento; só teste sintético separa os dois.

## Repositório socfortress/Wazuh-Rules (avaliado, não adotado)

2.212 regras em 50 pastas; último commit 11/03/2026. Medi só nomes, ids e níveis; não li o conteúdo regra a regra.

- **Colisão de ids:** `Windows_Sysmon/100100-…xml` e a faixa 100100–200070 usam o `100100` (nosso). Também `100001`/`100002` (Suricata, AWS). Id duplicado derruba o analysisd.
- **Sem licença** no repositório: uso em ambiente de cliente precisa ser resolvido com a SOCFortress antes de copiar regra.
- **Sem fonte aqui:** 1.135 regras de Sysmon (temos 0 eventos), Tetragon 297, Auditd 64, Osquery 53, Office 365 153 e conectores de terceiros.
- Sigma todo em nível ≥ 12, sem tuning (risco de repetir o ruído).
- `wazuh_socfortress_rules.sh` mexe no manager; não rodar em produção.

**Decisão:** não instalar nada na `homol`. No Wazuh novo, ligar Sysmon e auditoria de linha de comando (GPO) e só então trazer `Windows Powershell` (69) e `Windows_Sysmon`, revisados um a um, com licença resolvida. `Exclusion Rules` (ids 900000+) serve de modelo, medindo cada exclusão aqui.

## Para o Wazuh novo

1. Renumerar as nossas regras locais para `110000+` (livre no repositório acima) antes de importar qualquer conjunto externo.
2. Desenhar a coleta: Sysmon, 4688 com linha de comando, 4104, 1102, 4698.
3. Teste sintético dos eventos da lacuna antes de dar a cobertura como boa.
4. Revisar o FIM do registro (lista de chaves) e o nível da `60602`/`61061` depois do corte da Brother.

## Pendente

- Apagar `/home/ness_ro/wz_user.py`, `apply_100101.sh` e a pasta `conf/` na `homol`.
- Ler o `ossec.conf` de uma estação e de um servidor Windows (decide o que os agentes coletam hoje).
