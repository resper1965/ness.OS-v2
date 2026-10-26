# UAT de identidade e Zabbix — precheck somente leitura (2026-09-28)

Coleta em 2026-09-28, entre 19:36 e 19:39 UTC. Não houve login nominal, alteração de configuração, início de coleta ou escrita nas aplicações.

| Verificação | Resultado |
| --- | --- |
| Gate estático Authentik | `PASS` em `infra/tests/test-authentik-readiness.sh` |
| Controles estáticos da sessão Hub | `PASS`: cookie, borda e ausência de token no JavaScript; zero requisições de rede |
| Testes de sessão, OIDC, RBAC e dashboard | 60 aprovados |
| Saúde pública Authentik e página pública Hub | HTTP 200 em ambos |
| GLPI e n8n sem sessão | HTTP 302 para `sso.ness.com.br` em ambos |
| GLPI com cabeçalhos de identidade forjados | HTTP 302 para `sso.ness.com.br`; nenhuma sessão demonstrada |
| Zabbix UAT, rota SSO | HTTP 302 para `sso.ness.com.br` |
| Zabbix UAT por SSH | `zabbix-server`: `inactive` e `masked`; zero escutas TCP/10051 |

As verificações HTTP vieram de `infra/scripts/authentik-public-precheck.sh`, sem seguir redirects ou imprimir cabeçalhos. A checagem do serviço Zabbix executou apenas `systemctl is-active`, `systemctl is-enabled` e `ss` com a identidade `ness_admin` no host UAT.

**Limite:** esses resultados não comprovam login/MFA nominal, isolamento entre tenants na aplicação implantada, revogação, autorização GLPI ou integração real Zabbix → Hub → GLPI. A tentativa de acesso SSH somente leitura à VPS AIOps nesta sessão recebeu `Permission denied (publickey)`; backups e runtime de produção não foram revalidados. A Fase 0 permanece `FAIL`, sem autorização para deploy ou cutover.
