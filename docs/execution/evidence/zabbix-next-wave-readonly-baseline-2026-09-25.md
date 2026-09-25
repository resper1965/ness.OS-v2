# Baseline somente leitura para a próxima onda Zabbix — 2026-09-25

Coleta em 2026-09-25, aproximadamente 18:51 BRT. Consultas feitas pelos
serviços já configurados no Hub; tokens não foram exibidos nem registrados.
Nenhum host, item, trigger, template, histórico ou registro GLPI foi alterado.

## Proteção e gate

- Origem canônica confirmada pelo inventário Contabo: `144.91.72.202`,
  instância `203409070`, estado Contabo `running`.
- Último backup local Zabbix: conjunto `20260925T162305-0300`; serviço terminou
  às 17:02:33 BRT com código zero, manifesto e marcador `COMPLETED` presentes.
- Timer local habilitado e ativo; próxima execução prevista para 22:00 BRT.
- Timer externo `ness-zabbix-object-storage-backup.timer` segue desabilitado.
  Não foi feita consulta nem operação Restic/Object Storage.
- Gate da Fase 0 permanece `FAIL`; esta leitura não autoriza escrita.

## Alcance da identidade API atual

O token de integração Zabbix do Hub consegue consultar 260 hosts: 259
habilitados e 1 desabilitado. Esse número representa o escopo visível a essa
identidade e não prova a contagem total da instalação. O endpoint
`template.get` respondeu erro de aplicação; a relação de templates não ficou
verificada. Por isso, listas vazias de templates retornadas por `host.get` não
foram tratadas como prova de ausência de templates.

Para o grupo Cavan visível a essa identidade:

| Medida | Resultado |
|---|---:|
| Hosts | 28 |
| Habilitados / desabilitados | 27 / 1 |
| Sem tags diretas | 9 |
| Itens habilitados não suportados | 59 |
| Triggers desconhecidas | 72 |

## Candidato de piloto observado

O host `10977` está habilitado e corresponde ao FortiGate interno Cavan da
matriz (`172.29.0.254`). Grupos: Cavan, Matriz e Firewall. Tags diretas
confirmadas: tenant `cavan`, site `matriz-sp`, ambiente `production`, escopo
`customer`, owner `ricardo-esper`, função `firewall` e tecnologia
`fortigate-snmp`.

Leitura atual dos três hosts FortiGate Cavan:

| Host | Item | Estado do item | Triggers dependentes | Estado das triggers |
|---|---:|---|---|---|
| `10873` — AmericaNet | `97468` | habilitado, não suportado | `39192`, `39193` | habilitadas, desconhecidas |
| `10874` — Vivo | `97845` | habilitado, não suportado | `39307`, `39308` | habilitadas, desconhecidas |
| `10977` — firewall interno | `115583` | habilitado, não suportado | `49797`, `49798` | habilitadas, desconhecidas |

Nos três itens, a mensagem atual é divisão por zero em
`vfs.fs.pfree` ao usar `fgSysDiskCapacity.0`. As duas triggers de cada host são
“Free disk space is too low” e “Free disk space is low”. O estado `unknown`
foi observado sem evento ativo (`value=0`). A leitura confirma a evidência
anterior; não redefine a causa nem justifica substituir capacidade zero por um
percentual inventado.

## Pré-condições ainda ausentes

- O token atual não comprovou visibilidade de templates.
- A credencial GLPI usada pelo Hub vê somente um `NetworkEquipment` e um
  `Computer`; ela não localizou o marcador `Zabbix Host ID: 10977` na entidade
  Cavan. O vínculo GLPI do ativo não foi confirmado por essa identidade.
- O snapshot externo atual do Zabbix e o rollback associado continuam sem
  comprovação.

Assim, `10977` é apenas o candidato mais delimitado para preparar a onda, não
uma aprovação para alterar produção. Depois do gate, a próxima coleta deve usar
uma identidade de leitura com escopo suficiente para templates e para o ativo
GLPI da entidade Cavan. Só então exportar rollback e revalidar imediatamente os
IDs/statuses antes de qualquer escrita. Se aprovado nessa etapa, limitar o
piloto inicial a esse host e observar por 24–72 horas, conforme
`../decisions/zabbix-polish-wave-strategy-2026-09-25.md`.

## Revalidação do candidato em 19:18 BRT

Consulta somente leitura à API Zabbix pela integração existente no Hub; token não exibido. Os IDs continuam válidos e sem alteração desde o baseline:

- Host `10977` (`cavan-matriz-fgt40f`), habilitado, com tags de tenant/site/environment/scope/owner/role/technology iguais às listadas acima.
- Item `115583` (`vfs.fs.pfree`), habilitado e não suportado pela mesma divisão por zero em `fgSysDiskCapacity.0`.
- Triggers `49797` e `49798`, habilitadas, `value=0`, `state=1` (unknown), sem evento ativo confirmado.

Esta revalidação atualiza a identidade/status do candidato, mas não resolve visibilidade de templates, vínculo do ativo no GLPI, UAT ou Gate da Fase 0. Nenhuma escrita foi feita.
As chamadas de API foram consultas `get` de leitura segundo a
[documentação Zabbix 7.0](https://www.zabbix.com/documentation/7.0/en/manual/api).
