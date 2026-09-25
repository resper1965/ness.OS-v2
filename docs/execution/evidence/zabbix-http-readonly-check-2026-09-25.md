# Verificação HTTP/API somente leitura do Zabbix — 2026-09-25

Coleta em 2026-09-25, aproximadamente 18:24 BRT. Nenhuma autenticação foi
usada e nenhuma configuração ou dado foi alterado.

| Endpoint | Resultado |
|---|---|
| `https://zabbix-uat.ness.com.br/` | HTTP 200, página padrão do Apache Ubuntu. |
| `https://zabbix-uat.ness.com.br/zabbix/` | HTTP 200, frontend Zabbix (`ness.OS Zabbix: Zabbix`). |
| `https://zabbix-uat.ness.com.br/zabbix/api_jsonrpc.php` — `apiinfo.version` | Zabbix `7.0.27`. |
| `https://zabbix.ness.com.br/api_jsonrpc.php` — `apiinfo.version` | Zabbix `7.0.27`. |
| SSH direto para `144.91.72.202:22` deste ambiente | Timeout de conexão. |

## Interpretação e limite

A raiz do domínio UAT não é o caminho da aplicação; o frontend e a API estão
sob `/zabbix/`. O HTTP 200 da raiz, isoladamente, não verifica a aplicação.
Produção e UAT anunciam a mesma versão, mas `apiinfo.version` não comprova
inventário, estado dos hosts, timers de backup, snapshot externo ou paridade de
configuração. O timeout SSH também não confirma o estado do host. Assim, esta
checagem não altera o resultado FAIL do gate da Fase 0 nem autoriza a próxima
onda de mudanças.

## Próxima coleta necessária

Quando o acesso autenticado de leitura estiver disponível, coletar um baseline
API novo de produção e UAT. Separadamente, validar no host canônico o timer e o
snapshot externo do conjunto Zabbix atual. Manter a UAT em observação sem
alterações até passar pelos gates já definidos.
