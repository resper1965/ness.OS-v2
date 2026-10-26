# Baseline somente leitura para a próxima onda Zabbix — 2026-09-25

Coleta em 2026-09-25, aproximadamente 18:51 BRT. Consultas feitas pelos
serviços já configurados no Hub; tokens não foram exibidos nem registrados.
Nenhum host, item, trigger, template, histórico ou registro GLPI foi alterado.

## Proteção e gate

- Origem canônica confirmada pelo inventário Contabo: `144.91.72.202`,
  instância `203409070`, estado Contabo `running`.
- Baseline de backup desta coleta original: conjunto local
  `20260925T162305-0300`, terminado às 17:02:33 BRT com sucesso.
- Atualização em 26/09: conjunto `20260925T220022-0300` enviado ao snapshot
  `15a5ef41be82e65eda4fc5be285d948a1daeccd0c68f0a46ceb9090b168c190e`; cópia,
  `restic check` completo e restauração isolada passaram. Timers local e externo
  estão habilitados/ativos. A próxima execução externa é 27/09 às 05:30 BRT.
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
- A UAT responde em HTTP e anuncia Zabbix 7.0.27, mas não tem baseline API
  autenticado e corrente de inventário/status. A UAT deve continuar sem coleta
  de produção até esse baseline passar.

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

## Revalidação somente leitura pelo runtime AIOps em 26/09

Os probes já implantados no container `ninf-api` confirmaram Zabbix 7.0.27
autenticado e GLPI pela rota privada. O probe genérico Zabbix consulta
`host.get` com `limit=1`; portanto, `visible_hosts=1` nessa saída é tamanho da
amostra, não o total de hosts visíveis.

Consultas JSON-RPC somente leitura, feitas em seguida com a mesma identidade da
integração AIOps:

- `host.get` sem filtro retornou 260 hosts visíveis.
- `template.get` falhou com `No permissions to call "template.get"`; a lista de
  templates e a relação template-host permanecem não verificadas.
- `host.get` filtrado pelo ID `10977` encontrou o host, mas `selectParentTemplates`
  não retornou relações. Como a permissão de `template.get` está ausente, esse
  resultado não prova ausência de templates.
- O readiness GLPI concluiu por transporte privado: 12 entidades visíveis, 8
  categorias de conhecimento e sessão encerrada; zero alterações em registros.
- A leitura inicial das coleções `Computer` e `NetworkEquipment` no contexto
  ativo padrão retornou um registro de cada tipo, sem o marcador procurado.
- Em uma sessão temporária separada, `getMyEntities` mostrou uma única entidade
  Cavan autorizada (`Ness Processos e Tecnologia Ltda. > Cavan`, ID `8`). Selecionei
  esse contexto com `changeActiveEntities` apenas para a sessão, sem alterar
  registros, e repeti as leituras: 19 `Computer`, 9 `NetworkEquipment`, com
  exatamente um marcador `Zabbix Host ID: 10977` em `NetworkEquipment`. A sessão
  foi encerrada. O vínculo GLPI do candidato está confirmado para essa identidade.

Conclusão: baseline de hosts confirmada em 260, snapshot/restore externo atual
aprovados e vínculo GLPI do candidato confirmado. A visibilidade de templates
continua bloqueada por permissão explícita, e falta baseline autenticado atual
da UAT. Nenhum host, ativo ou outro registro foi alterado.

## Revalidação da API canônica e UAT em 26/09

Consultas adicionais entre 19:11 e 19:18 UTC (16:11–16:18 BRT), sem exibir o
token da integração e sem chamar métodos de escrita:

- A API canônica confirmou 260 hosts visíveis: 259 com `status=0` e 1 com
  `status=1`. `template.get` continua falhando com
  `No permissions to call "template.get"`.
- Na UAT, `apiinfo.version` sem autenticação retornou `7.0.27`. O token usado
  pela integração canônica retornou `Not authorized` para `host.get` e
  `template.get`; não existe ainda baseline API autenticado da UAT.
- A UAT segue com `zabbix-server` inativo e mascarado, sem listener em `10051`.
  Contagem somente leitura no banco restaurado: 203 tabelas, 677 linhas em
  `hosts`, 61.859 em `items` e 25.274 em `triggers`. Valores por `status`, schema
  e versões estão em
  [`zabbix-uat-readonly-baseline-2026-09-26.md`](zabbix-uat-readonly-baseline-2026-09-26.md).

Esta atualização demonstra que o endpoint de produção continua visível ao
token, mas não amplia seu privilégio para templates e não autentica a cópia UAT.
Nenhum objeto Zabbix foi alterado.
