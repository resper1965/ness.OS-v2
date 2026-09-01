# Verificação dos ativos usados como contexto no incidente Zabbix

> Data: 21/08/2026
> Método: correlação somente leitura da evidência preservada com hosts, interfaces, inventário, itens e proxies atuais do Zabbix. Nenhum comando foi enviado aos ativos.

## Conclusão

O audit log preservado contém 266 execuções com oito hosts usados como contexto. Todos os registros analisados possuem `script.execute_on=1`; no Zabbix 7.0 isso executa no **servidor Zabbix**, não no host selecionado. A classificação dos alvos reduz ainda mais a hipótese de execução direta: quatro são interfaces Fortigate por SNMP e dois são Windows Server 2019, enquanto os payloads observados eram Bash/Linux.

A correlação de contexto está concluída, mas a verificação direta de endpoint não está totalmente encerrada. O proxy Linux de Lima precisa de inspeção por SSH/console/RMM por um responsável local: o processo proxy continua comunicando, porém o agente associado ao host está indisponível e sua telemetria de sistema não possui valores recentes.

## Contextos identificados

| Host ID | Contexto | Execuções | Tipo observado | Estado da monitoração | Decisão |
|---:|---|---:|---|---|---|
| 10084 | Zabbix Server | 124 | Debian Linux | agente disponível | servidor já contido, inspecionado e com evidências preservadas |
| 10684 | Proxy Zabbix Lima (`alppezbxprx`) | 24 | host Linux atrás do proxy 2 | agente indisponível; proxy `alppeliprx` comunicando | inspeção direta obrigatória |
| 10687 | Fortigate Anserma — Azteca | 21 | SNMP | disponível | payload Linux incompatível; revisar configuração/login administrativo apenas como higiene |
| 10688 | Fortigate Anserma — InterLAN | 21 | SNMP | disponível | payload Linux incompatível; revisar configuração/login administrativo apenas como higiene |
| 10693 | Fortigate Bogotá — ETB | 19 | SNMP | disponível | payload Linux incompatível; revisar configuração/login administrativo apenas como higiene |
| 10694 | Fortigate Bogotá — IFX | 19 | SNMP | disponível | payload Linux incompatível; revisar configuração/login administrativo apenas como higiene |
| 10695 | `ALPCOLAP11` | 19 | Windows Server 2019 | agente disponível; zero itens não suportados | payload Bash/Linux incompatível; executar varredura IOC via RMM/EDR como confirmação |
| 10696 | `ALPCOLAPH1` | 19 | Windows Server 2019 | agente disponível; 21 itens não suportados | payload Bash/Linux incompatível; executar varredura IOC via RMM/EDR e corrigir coleta |

Os proxies `alpcolprx` e `alppeliprx` estavam em modo ativo, versão 7.0.28 e com `lastaccess` atual no momento da consulta.

## IOCs para a verificação direta

- processo/binário: `xmrig`, `zbx_cron_health`, `.zbx_sys_health`;
- caminhos: `/var/tmp/.zbx_sys_health`, `/tmp`, `/var/tmp`, `/dev/shm`;
- persistência: cron do usuário de serviço, `@reboot`, units systemd e chaves SSH recentes;
- rede: IPs e domínios registrados em [`../../infra/docs/incidents/2026-08-20-zabbix-xmrig-compromise.md`](../../infra/docs/incidents/2026-08-20-zabbix-xmrig-compromise.md);
- contas: usuários administrativos novos, UID 0 adicional e alteração de `authorized_keys`.

## Ações pendentes

1. Identificar quem possui acesso administrativo ao proxy Lima e qual RMM está instalado nele.
2. Executar coleta IOC no proxy por ferramenta administrativa fora do Zabbix; preservar resultado, horário, operador e hashes.
3. Executar consulta equivalente nos dois Windows por RMM/EDR, incluindo processos, serviços, tarefas agendadas, conexões e arquivos recentes.
4. Revisar logs administrativos/configuração dos quatro Fortigate somente para afastar comprometimento independente; não há evidência de execução pelos registros Zabbix.
5. Corrigir o agente indisponível do host 10684 e os 21 itens não suportados do host 10696 na fase de polimento.

## Ferramenta reproduzível

O relatório foi gerado por [`../../infra/scripts/zabbix-incident-context-report.sh`](../../infra/scripts/zabbix-incident-context-report.sh). O script extrai os host IDs diretamente da evidência compactada e faz somente `SELECT` no banco, usando a credencial já protegida no arquivo de configuração sem imprimi-la.
