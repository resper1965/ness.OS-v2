# Baseline atual somente leitura da UAT Zabbix — 2026-09-26

Coleta em 2026-09-26, entre 19:11 e 19:18 UTC (16:11–16:18 BRT), na UAT
`169.58.234.9` (`zbx-prd-01`). A autenticação SSH foi feita como `ness_admin`
com a chave nominal específica da UAT. `npentest` não foi acessada.

## Host, serviços e banco

- `apache2`: ativo. `zabbix-server`: inativo e mascarado.
- Listeners observados: Apache em `127.0.0.1:8080` e `*:443`; MariaDB em
  `127.0.0.1:3306`; Zabbix Agent em `*:10050`. Não há listener em `10051`.
- Versões: Zabbix Server `7.0.27`; MariaDB `10.11.19-MariaDB`.
- Consultas somente leitura ao banco `dbzabbix`: 203 tabelas;
  `dbversion.mandatory=7000000`, `optional=7000030`.
- Estado bruto por coluna de status:

  | Tabela | Status | Registros |
  |---|---:|---:|
  | `hosts` | 0 | 314 |
  | `hosts` | 1 | 1 |
  | `hosts` | 3 | 362 |
  | `items` | 0 | 61.616 |
  | `items` | 1 | 243 |
  | `triggers` | 0 | 25.167 |
  | `triggers` | 1 | 107 |

  Totais: 677 linhas em `hosts`, 61.859 em `items` e 25.274 em `triggers`.

## API e autenticação

- A consulta JSON-RPC `apiinfo.version` pelo túnel SSH local para
  `127.0.0.1:8080/zabbix/api_jsonrpc.php` retornou `7.0.27`.
- `host.get` e `template.get` com o token da integração existente no AIOps
  retornaram `Not authorized` na UAT. O token não foi mostrado nem registrado.
  Portanto, a versão HTTP e a leitura do banco não substituem um baseline API
  autenticado da UAT. Nenhum token ou usuário foi criado e nenhuma permissão foi
  alterada.
- No endpoint canônico `https://zabbix.ness.com.br/api_jsonrpc.php`, o token
  atual da integração retornou 260 hosts visíveis (259 com `status=0`, 1 com
  `status=1`). `template.get` continua negado com
  `No permissions to call "template.get"`.

As chamadas API foram JSON-RPC de leitura com `Authorization: Bearer`; o
`apiinfo.version` foi consultado sem autenticação. O túnel SSH seguiu o runbook
de UAT e foi encerrado após a coleta. Nenhuma coleta Zabbix foi iniciada e
nenhum host, item, trigger, template, usuário, token ou registro GLPI foi
alterado.

## Resultado

A UAT está alcançável por SSH e sua cópia segue isolada, com `zabbix-server`
mascarado. Permanecem bloqueios separados: não há identidade API autorizada
para ler inventário da UAT, o token canônico não pode consultar templates e o
Zabbix canônico não foi alcançado por SSH nesta sessão. Esta evidência não
autoriza piloto de coleta ou cutover.
