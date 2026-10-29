# Wazuh: revisão de regras (29/10/2026)

Legenda: o que está em "Medido", contagens e tabelas vem de leitura (Wazuh, repositórios clonados em 29/10); "Minha leitura", "pelo que li" e "confirmar" são opinião ou não verificado.

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

2.212 regras em 53 pastas com XML; último commit 11/03/2026. Medi só nomes, ids e níveis (contagem por `<rule`); não li o conteúdo regra a regra.

- **Colisão de ids (medida):** `Windows_Sysmon` (1.135 regras, ids 100100–200070) usa o `100100` e o `100101`, os dois nossos. `Suricata/100002` colide com o exemplo `100002` do `local_rules.xml` padrão. Os ids 100000–109999 têm 1.223 regras do conjunto, 110000–119999 têm 188. Id duplicado impede o analysisd de carregar as regras (comportamento do Wazuh; confirmar na documentação antes de citar a terceiros).
- **Sem arquivo de licença** no repositório (a API do GitHub não detecta nenhuma). O README mostra um selo "MIT License", mas o link do selo aponta para o suporte da SOCFortress, não para um texto de licença. Tecnicamente sem licença; **uso liberado pelo Ricardo (jurídico) em 29/10/2026**, sem consulta à SOCFortress. Registro da decisão, não texto de licença.
- **Sem fonte aqui:** 1.135 regras de Sysmon (temos 0 eventos), Tetragon 297, Auditd 64, Osquery 53, Office 365 153 e conectores de terceiros.
- `Windows Sigma Rules` (7 regras): todas em nível 15, sem tuning (risco de repetir o ruído). Em `Windows_Sysmon` e `Windows Powershell` a maioria está em nível 10 (793 de ~1.200) e 3 (378).
- `wazuh_socfortress_rules.sh` mexe no manager; não rodar em produção.

**Decisão:** não instalar nada na `homol`. No Wazuh novo, ligar Sysmon e auditoria de linha de comando (GPO) e só então trazer `Windows Powershell` (69) e `Windows_Sysmon`, revisados um a um (licença liberada). `Exclusion Rules` (ids 900000+) serve de modelo, medindo cada exclusão aqui.

## SigmaHQ/sigma (avaliado, uso restrito)

Último commit 21/10/2026. Licença das regras: Detection Rule License (DRL) 1.1, que permite uso e modificação com atribuição ao autor; uso **liberado pelo Ricardo (jurídico) em 29/10/2026**.

Medido nos arquivos do repositório: 2.425 regras de Windows em `rules/windows` (3.161 em `rules/` ao todo). `rules-emerging-threats` é à parte: 474 regras, 324 de Windows, não contadas abaixo. A classificação por exigência é minha (pelo `logsource`); fronteiras como Sysmon×canal nativo mudam alguns dezenas de casos, o total não.

| Exige | Regras | Funciona hoje? |
|---|---|---|
| `process_creation` | 1.193 | Não: precisa de Sysmon (evento 1) ou do 4688 com linha de comando (hoje 0) |
| Sysmon (registro, arquivo, DLL, rede, pipe, DNS…) | 681 | Não: 0 eventos de Sysmon |
| PowerShell (4103/4104) | 211 | Não: 4104 em 0 |
| Canal nativo (Security 146, System 63, Application 23, Defender 16…) | 309 | Em parte; é a única fatia sem nova coleta |
| Outros (sem categoria clara) | 31 | Não avaliado |

No máximo ~13% (309/2.425 = 12,7%) das regras de Windows teriam dado com a coleta de hoje: é teto, não medida, porque o `ossec.conf` dos agentes não foi auditado (ver Pendente) e "em parte" já está contado como inteiro. Nível: 1.176 high e 58 critical em 2.425; status: 2.192 `test`, só 54 `stable`.

**Não são regras do Wazuh.** O Sigma é formato de consulta. Não encontrei backend oficial do pySigma para o Wazuh (confirmar). Minha leitura: o motor do Wazuh encadeia regras por `if_sid` com condições AND, então o OR do Sigma não converte direto. Conversores existentes (`theflakes/sigma_to_wazuh`, MIT) declaram converter ~88% (número do README deles, não testado aqui) e precisam de ajuste manual. Os ids gerados seriam um problema novo de colisão.

**Decisão:** o Sigma não é o caminho para o Wazuh. Serve como catálogo de detecções para escolher quais eventos coletar e como referência para escrever poucas regras próprias, com id `150000+` e cada uma testada com evento sintético. Para usá-lo em escala, o caminho é o Chainsaw (Sigma sobre os logs) em análise forense, fora do Wazuh. Revisitar na versão 5.0 do Wazuh, que pelo que li muda o motor de regras (confirmar).

**Ordem para cobertura:** (1) ligar Sysmon e 4688/4104 no Wazuh novo; (2) escolher ~30 detecções do Sigma por técnica MITRE (persistência, credenciais, ransomware, limpeza de log); (3) escrevê-las como regras locais com teste.

## Para o Wazuh novo

1. Renumerar as nossas regras locais para `150000+` (130000–199999 não tem regra no repositório acima; `110000–119999` tem 188) antes de importar qualquer conjunto externo.
2. Desenhar a coleta: Sysmon, 4688 com linha de comando, 4104, 1102, 4698.
3. Teste sintético dos eventos da lacuna antes de dar a cobertura como boa.
4. Revisar o FIM do registro (lista de chaves) e o nível da `60602`/`61061` depois do corte da Brother.

## Pendente

- Apagar `/home/ness_ro/wz_user.py`, `apply_100101.sh` e a pasta `conf/` na `homol`.
- Ler o `ossec.conf` de uma estação e de um servidor Windows (decide o que os agentes coletam hoje).
