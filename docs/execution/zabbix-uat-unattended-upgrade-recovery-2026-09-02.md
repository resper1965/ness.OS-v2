# Recuperação do upgrade automático no Zabbix UAT — 02/09/2026

## Sintoma

O precheck público da onda F2 encontrou HTTP 404 na rota desatualizada
`/index_sso.php` e `Database error — No such file or directory` na rota efetiva
`/zabbix/index_sso.php` do destino `zbx-prd-01` (`169.58.234.9`).

## Causa comprovada

`apt-daily-upgrade` iniciou às 06:45 BRT e o `needrestart` enfileirou um restart
conjunto de serviços. Às 06:47, o MariaDB encerrou normalmente, mas o
`zabbix-server` ficou em `deactivating` por mais de dez horas:

- a unit tinha `TimeoutStopSec=infinity`;
- filhos do Zabbix continuavam tentando reconectar ao socket ausente do banco;
- o job de start do MariaDB aguardava o restart preso do Zabbix;
- TCP/10051 permaneceu aberto, embora não houvesse conexão estabelecida no
  instante da inspeção;
- o frontend ficou sem banco e o upgrade automático não concluiu.

O destino UAT deve permanecer isolado. A produção reativada e o DNS público
continuam na origem `144.91.72.202`; nenhum DNS foi alterado nesta recuperação.

## Contenção executada

1. cancelado somente o job de restart preso do `zabbix-server`;
2. unit mascarada novamente para impedir partida automática;
3. MariaDB iniciado para permitir o encerramento gracioso dos processos;
4. parada do Zabbix concluída sem `SIGKILL`;
5. marcador `failed` transitório limpo, preservando `inactive/masked`.

## Verificação

- MariaDB: `active/enabled`, socket saudável e TCP/3306 somente localhost;
- Zabbix Server: `inactive/masked`, sem processo e sem listener TCP/10051;
- SAML UAT: `/zabbix/index_sso.php` voltou a HTTP 302 para
  `sso.ness.com.br`;
- banco restaurado preservado: 203 tabelas, 677 hosts, zero action, media type
  ou connector habilitado;
- Authentik, Hub, GLPI e n8n não foram modificados;
- o upgrade automático retomou e terminou com `Result=success` às 17:35:48;
- `dpkg --audit` e `apt-get check` passaram; o marcador transitório de
  `apt-daily` por disputa do lock foi limpo e nenhuma unit ficou falha.

## Pendência preventiva

A correção permanente está na issue #57: timeout finito testado, exclusão do
restart automático durante staging/migração e alerta para upgrade preso. O bug
de disponibilidade/SSO foi recuperado na issue #56 e a homologação F2 permanece
na #51.

As duas primeiras proteções foram preparadas como arquivos independentes e
reversíveis:

- `infra/systemd/zabbix-server-stop-timeout.conf`: limita a parada a cinco
  minutos;
- `infra/needrestart/ness-zabbix-staging.conf`: impede restart automático do
  `zabbix-server` pelo `needrestart` durante staging/cutover.

Remover somente esses dois arquivos e executar `systemctl daemon-reload` é o
rollback de configuração. O alerta de upgrade preso continua pendente na #57.
