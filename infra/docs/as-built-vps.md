# Estado real das VPS (as built)

> **Estado atual:** seção [Snapshot de 27/10/2026](#snapshot-de-27102026), gerada por `infra/scripts/as-built-collect.sh`. O texto abaixo dela é o levantamento manual de 20/08 e fica como histórico.
>
> Levantamento somente leitura realizado em 20/08/2026. Este documento descreve o estado observado nessa data; não substitui monitoramento contínuo. Valores secretos foram deliberadamente omitidos.

## Escopo e acesso administrativo

| Função | Endereço | Sistema | Acesso SSH validado |
|---|---|---|---|
| Zabbix/NOC | `144.91.72.202` | Debian 12 (bookworm) | `ness_admin`, porta `2222`, chave SSH e `sudo` sem prompt |
| Hub AIOps | `144.91.115.242` | Debian 12 (bookworm) | `root`, porta `22`, chave SSH |

As chaves privadas não ficam no repositório e não devem ser copiadas para esta documentação.

## VPS Zabbix/NOC

> Acesso após Gate 0: `ness_admin` por chave SSH na porta 2222; senha e login root por SSH desativados. A credencial root rotacionada permanece temporariamente para console/resgate em arquivo root protegido na VPS, aguardando migração para cofre corporativo externo.

### Capacidade observada

| Item | Estado observado |
|---|---|
| Hostname | `zabbix-srv01` |
| Virtualização | KVM/QEMU |
| CPU | 8 vCPU |
| Memória | 29 GiB; swapfile persistente de 8 GiB, `vm.swappiness=10` |
| Disco raiz | 1,2 TB ext4; aproximadamente 40 GB usados na coleta |
| Kernel | `6.1.0-49-cloud-amd64` |
| Fuso/NTP | `America/Sao_Paulo`; NTP sincronizado |

### Componentes instalados

| Componente | Versão/estado observado |
|---|---|
| Zabbix Server | `7.0.27`, ativo e habilitado |
| Zabbix Agent 2 | `7.0.27`, ativo e habilitado |
| Zabbix frontend | `7.0.27` sobre Apache/PHP |
| MariaDB | `10.11.18`, ativo e habilitado |
| Apache | `2.4.68`, ativo e habilitado |
| PHP | `8.2.33` |
| Certbot | `2.1.0` |
| Fail2ban | `1.0.2`, ativo e habilitado |
| UFW | ativo, política de entrada `deny` |
| rclone | `1.60.1` instalado |

O banco configurado pelo Zabbix é `dbzabbix`, com usuário de aplicação `usrzabbix`. O diretório de dados do banco ocupava aproximadamente 34 GB na coleta.

### Rede e publicação

| Porta | Finalidade | Publicação observada |
|---|---|---|
| `2222/tcp` | SSH administrativo | UFW permite IPv4 e IPv6 |
| `80/tcp` | HTTP/redirect | UFW permite IPv4 e IPv6 |
| `443/tcp` | Frontend Zabbix HTTPS | UFW permite IPv4 e IPv6 |
| `10051/tcp` | Zabbix Server/Trapper | UFW permite IPv4 e IPv6 |
| `10050/tcp` | Zabbix Agent 2 | serviço escutando; não há regra UFW pública específica |
| `3306/tcp` | MariaDB | limitado a `127.0.0.1` |
| `161/udp` | SNMP local | limitado a loopback |

O certificado observado atende `zabbix.ness.com.br`. A renovação é executada por `certbot.timer` e também por cron às 02:30 e 14:30, com reload do Apache. Essa duplicidade deve ser simplificada em manutenção futura.

### Persistência e backup

- A aplicação e o banco são serviços nativos do host, não contêineres.
- A configuração principal está em `/etc/zabbix`, `/etc/apache2`, `/etc/mysql/mariadb.conf.d` e `/etc/fail2ban`.
- `rclone` está instalado, mas o playbook de backup está comentado em `infra/ansible/playbooks/site.yml`.
- Não foi encontrado dump do banco nem diretório `/backup`; apenas backups automáticos de metadados do Debian em `/var/backups`.
- Portanto, no estado observado, não há evidência de backup operacional do banco Zabbix.

## VPS Hub AIOps

> Acesso após Gate 0: `ness_admin` por chave SSH com `sudo`; novas sessões root, senha e keyboard-interactive estão desativadas. A credencial root rotacionada permanece temporariamente para console/resgate em arquivo root protegido na VPS, aguardando migração para o Passbolt.

### Capacidade observada

| Item | Estado observado |
|---|---|
| Hostname | `vmi3409271` |
| Virtualização | KVM/QEMU |
| CPU | 8 vCPU |
| Memória | 23 GiB; swapfile persistente de 4 GiB, `vm.swappiness=10` |
| Disco raiz | 400 GB ext4; aproximadamente 37 GB usados na coleta |
| Kernel | `6.1.0-52-cloud-amd64` |
| Docker Engine | `29.6.1` |
| Docker Compose | `v5.2.0` |

### Forma real de implantação

A implantação está em `/opt/n-infraops/app`. O diretório `/opt/n-infraops` não é um checkout Git; os arquivos são transferidos para a VPS. Os 14 serviços ativos correspondem aos arquivos principal e de tickets:

```bash
docker compose \
  -f docker-compose.yml \
  -f docker-compose.tickets.yml \
  up -d --build
```

Na coleta inicial, o metadata do projeto Compose ainda referenciava um terceiro arquivo de uma integração já desativada. Seus dois contêineres não estavam ativos. Em 20/08/2026, os arquivos, imagens e referências residuais dessa integração foram removidos.

O `Caddyfile` da VPS era diferente do `app/Caddyfile` local, portanto mudanças de roteamento precisam ser reconciliadas antes do próximo deploy.

### Contêineres observados

| Contêiner | Imagem/base | Responsabilidade | Persistência principal |
|---|---|---|---|
| `ninf-api` | `app-api` | API FastAPI | bind mount do código backend |
| `ninf-worker-alerts` | `app-worker-alerts` | Celery de alertas | bind mount do código backend |
| `ninf-worker-ml` | `app-worker-ml` | Celery de ML/análise | bind mount do código backend |
| `ninf-frontend` | `app-frontend` | Dashboard React/Vite | imagem do contêiner |
| `ninf-postgres` | `timescale/timescaledb:latest-pg16` | PostgreSQL/TimescaleDB | `app_pg-data` |
| `ninf-redis` | `redis:7-alpine` | cache, broker e locks | `app_redis-data` |
| `ninf-n8n` | `docker.n8n.io/n8nio/n8n:latest` | workflows | `app_n8n-data` |
| `ninf-authentik-server` | `ghcr.io/goauthentik/server:2026.5.6` | SSO/IdP | volumes de mídia, templates e certificados |
| `ninf-authentik-worker` | `ghcr.io/goauthentik/server:2026.5.6` | tarefas do Authentik | volumes compartilhados do Authentik |
| `ninf-evolution` | `evoapicloud/evolution-api:latest` | WhatsApp API | `app_evolution-instances`, `app_evolution-store` |
| `ninf-evolution-manager` | `evoapicloud/evolution-manager:latest` | gestão da Evolution API | sem volume observado |
| `ninf-caddy` | `caddy:2-alpine` | proxy reverso/TLS | `app_caddy-data`, `app_caddy-config` |
| `ninf-glpi` | `elestio/glpi:latest` | GLPI/Service Desk | `app_glpi-data` e um volume anônimo legado |
| `ninf-glpi-db` | `mariadb:10.11` | banco do GLPI | `app_glpi-db-data` |

Todos usam a rede bridge `app_ninf-net`. Os bancos observados no PostgreSQL eram `authentik` (121 MB), `evolution` (31 MB), `nessops` (15 MB) e `postgres`; o MariaDB do GLPI ocupava aproximadamente 62 MB.

### Roteamento e publicação

| Domínio/porta | Destino observado |
|---|---|
| `hub.ness.com.br` | frontend e rotas da API |
| `api.ness.com.br` | `ninf-api:8000` |
| `n8n.ness.com.br` | `ninf-n8n:5678` |
| `sso.ness.com.br` | `ninf-authentik-server:9000` |
| `waba.ness.com.br` | `ninf-evolution:8080` |
| `n-ticket.ness.com.br` | `ninf-glpi:80` |
| `8082/tcp` | publicação removida em 20/08/2026; acesso somente pelo Caddy/rede interna |
| `8085/tcp` | publicação removida em 20/08/2026; acesso somente pelo Caddy/rede interna |

Na verificação externa, os seis domínios responderam; `/docs` da API retornou `401`, coerente com documentação protegida. Em 20/08/2026, as publicações Docker de 8082 e 8085 foram removidas, os serviços foram recriados e o fechamento externo foi validado.

### Persistência e backup

- Foram encontrados 13 volumes Docker, incluindo dados do PostgreSQL, Redis, n8n, Authentik, Evolution e GLPI.
- A inspeção inicial não encontrou rotina operacional de backup.
- Em 20/08/2026 foi instalado `ness-aiops-backup.timer`, diário às 23:00 BRT. O job gera dumps lógicos PostgreSQL/MariaDB, arquiva configurações e volumes não relacionais, pausa brevemente n8n/GLPI para consistência, valida `pg_restore`, gzip, tar e SHA-256 e só então cria o marcador `COMPLETED`.
- A execução de validação em `/opt/n-infraops/backups/nightly/20260820T170823-0300` incluiu `app_n8n-data`, `app_glpi-data` e o volume anônimo real do GLPI; todos os serviços foram religados.
- O backup permanece apenas local até configuração de Object Storage e criptografia off-site.
- O Hub depende de tags `latest` em várias imagens; isso reduz a reprodutibilidade de reinstalações.

## Diferenças entre documentação e produção

1. A arquitetura anterior descreve 12 contêineres; a produção executa 14, pois GLPI e MariaDB também fazem parte da stack.
2. O guia antigo de implantação esperava apenas seis contêineres e não incluía `docker-compose.tickets.yml`.
3. O guia dizia que `infra/ansible/playbooks/site.yml` poderia instalar Docker no Hub. Esse playbook instala a VPS Zabbix e não instala Docker.
4. `app/setup_hub.sh` executa hardening e cria diretórios, mas não instala Docker, apesar de listar `docker compose up` como próximo passo.
5. O Terraform define recursos para Zabbix, AIOps Hub, Wazuh Hub e Wazuh Spoke, enquanto o escopo operacional confirmado atualmente contém estas duas VPS.
6. O repositório local contém scripts avulsos de mudanças em GLPI, Authentik, SAML/OIDC e integrações. Eles registram partes do histórico, mas não formam uma migração idempotente.

## Riscos e ações prioritárias

| Prioridade | Achado | Ação recomendada |
|---|---|---|
| Crítica | Senhas reais aparecem em scripts e arquivos de resultado locais, inclusive comandos SSH e acesso ao GLPI | Rotacionar imediatamente as credenciais afetadas; remover segredos dos arquivos e do histórico Git; adotar cofre/variáveis protegidas |
| Alta | Não há evidência de backup operacional dos bancos/volumes nas duas VPS | Implantar backup versionado, criptografado, externo e testar restauração |
| Alta | Fail2ban do Hub está em estado `failed` porque o jail SSH não encontra o arquivo de log | Ajustar o backend do jail para `systemd`/journal e validar o banimento |
| Alta | Portas `8082` e `8085` são publicadas em `0.0.0.0` | Remover a publicação direta ou limitar a loopback/rede administrativa |
| Média | `Caddyfile` local e remoto divergentes | Tornar o repositório a fonte única e implantar por pipeline controlado |
| Média | Imagens usam `latest` | Fixar versões ou, preferencialmente, digests |
| Média | O Hub é acessado diretamente como `root` | Criar usuário administrativo nominal com `sudo`, restringir root e manter recuperação de emergência |
| Mitigado em 20/08/2026 | Ausência de swap nas duas VPS | Swapfile de 8 GiB no Zabbix e 4 GiB no AIOps, persistentes e com `swappiness=10`; monitorar uso e latência |
| Baixa | Certbot é acionado por timer e cron na VPS Zabbix | Manter apenas um mecanismo de renovação |

## Verificação segura após mudanças

```bash
# VPS Zabbix
systemctl --failed
systemctl status mariadb zabbix-server zabbix-agent2 apache2 fail2ban
sudo ufw status verbose

# VPS AIOps, a partir de /opt/n-infraops/app
docker compose \
  -f docker-compose.yml \
  -f docker-compose.tickets.yml \
  ps
systemctl --failed
sudo ufw status verbose
```

## Snapshot de 27/10/2026

Gerado por `NESS_AGENT_KEY=~/.ssh/nessos_agent infra/scripts/as-built-collect.sh <host> [porta]` (só leitura). Para atualizar, rode de novo e substitua esta seção.




### zabbix-srv01 (Debian GNU/Linux 12 (bookworm))

Coletado em 2026-10-27 08:44 -03.

#### Sistema

```
kernel 6.1.0-54-cloud-amd64
cpu 8 vCPU
Mem: 29Gi usado 21Gi
Swap: 8.0Gi usado 0B
America/Sao_Paulo yes
```

#### Disco

```
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/sda1      ext4  1.2T  311G  823G  28% /
/dev/sda15     vfat  124M   12M  112M  10% /boot/efi
```

#### Serviços (ativos e habilitados)

```
ssh                active    enabled
sshd               active    alias
ufw                active    enabled
fail2ban           active    enabled
systemd-timesyncd  active    enabled
mariadb            active    enabled
mysql              active    alias
zabbix-server      active    enabled
zabbix-agent2      active    enabled
```

#### Timers

```
apt-daily-upgrade.timer apt-daily-upgrade.service
apt-daily.timer apt-daily.service
dpkg-db-backup.timer dpkg-db-backup.service
e2scrub_all.timer e2scrub_all.service
exim4-base.timer exim4-base.service
fstrim.timer fstrim.service
man-db.timer man-db.service
ness-zabbix-backup.timer ness-zabbix-backup.service
ness-zabbix-object-storage-backup.timer ness-zabbix-object-storage-backup.service
phpsessionclean.timer phpsessionclean.service
systemd-tmpfiles-clean.timer systemd-tmpfiles-clean.service
```

#### Portas em escuta (fora de loopback)

```
80 * apache2
443 * apache2
2222 0.0.0.0 sshd
5355 0.0.0.0 systemd-resolve
10050 * zabbix_agent2
10051 0.0.0.0 zabbix_server
```

#### UFW

```
Status: active
Anywhere                   DENY        202.61.130.107             # Zabbix-IR-20260820
Anywhere                   DENY        111.34.138.86              # Zabbix incident 2026-08-20
Anywhere                   DENY        36.234.157.166             # Zabbix incident 2026-08-20
Anywhere                   DENY        37.153.90.88               # Zabbix incident 2026-08-20
Anywhere                   DENY        166.88.227.34              # Zabbix incident 2026-08-20
Anywhere                   DENY        202.61.130.55              # Zabbix incident 2026-08-20
Anywhere                   DENY        111.90.158.58              # Zabbix incident 2026-08-20
2222/tcp                   ALLOW       Anywhere                   # SSH - porta customizada
80/tcp                     ALLOW       Anywhere                   # HTTP
443/tcp                    ALLOW       Anywhere                   # HTTPS
10051/tcp                  ALLOW       Anywhere                   # Zabbix Trapper
2222/tcp (v6)              ALLOW       Anywhere (v6)              # SSH - porta customizada
80/tcp (v6)                ALLOW       Anywhere (v6)              # HTTP
443/tcp (v6)               ALLOW       Anywhere (v6)              # HTTPS
10051/tcp (v6)             ALLOW       Anywhere (v6)              # Zabbix Trapper
151.245.90.135             DENY OUT    Anywhere                   # Zabbix-IR-20260820
111.90.139.202             DENY OUT    Anywhere                   # Zabbix-IR-20260820
111.90.158.58              DENY OUT    Anywhere                   # Zabbix-IR-20260820
```

### vmi3409271 (Debian GNU/Linux 12 (bookworm))

Coletado em 2026-10-27 08:44 -03.

#### Sistema

```
kernel 6.1.0-54-cloud-amd64
cpu 8 vCPU
Mem: 23Gi usado 3.8Gi
Swap: 4.0Gi usado 2.0Mi
America/Sao_Paulo yes
```

#### Disco

```
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/sda1      ext4  394G  115G  263G  31% /
/dev/sda15     vfat  124M   12M  112M  10% /boot/efi
```

#### Serviços (ativos e habilitados)

```
ssh                active    enabled
sshd               active    alias
ufw                active    enabled
fail2ban           active    enabled
docker             active    enabled
containerd         active    enabled
systemd-timesyncd  active    enabled
```

#### Timers

```
apt-daily-upgrade.timer apt-daily-upgrade.service
apt-daily.timer apt-daily.service
dpkg-db-backup.timer dpkg-db-backup.service
e2scrub_all.timer e2scrub_all.service
exim4-base.timer exim4-base.service
fstrim.timer fstrim.service
man-db.timer man-db.service
ness-aiops-backup.timer ness-aiops-backup.service
ness-aiops-object-storage-backup.timer ness-aiops-object-storage-backup.service
ness-aiops-restore-verify.timer ness-aiops-restore-verify.service
ness-hub-cmdb-sync.timer ness-hub-cmdb-sync.service
ness-hub-integration-monitor.timer ness-hub-integration-monitor.service
ness-psono-backup.timer ness-psono-backup.service
ness-psono-restore-verify.timer ness-psono-restore-verify.service
systemd-tmpfiles-clean.timer systemd-tmpfiles-clean.service
```

#### Portas em escuta (fora de loopback)

```
22 0.0.0.0 sshd
80 0.0.0.0 docker-proxy
443 0.0.0.0 docker-proxy
5355 0.0.0.0 systemd-resolve
```

#### UFW

```
Status: active
22/tcp                     ALLOW       Anywhere                  
80/tcp                     ALLOW       Anywhere                  
443/tcp                    ALLOW       Anywhere                  
22/tcp (v6)                ALLOW       Anywhere (v6)             
80/tcp (v6)                ALLOW       Anywhere (v6)             
443/tcp (v6)               ALLOW       Anywhere (v6)             
```

#### Contêineres

```
ness-psono	psono/psono-combo:latest	Up 17 hours (healthy)
ness-psono-db	postgres:17-alpine	Up 17 hours (healthy)
ninf-api	31a99dc9460e	Up 15 minutes (healthy)
ninf-authentik-server	ghcr.io/goauthentik/server:2026.5.6	Up 17 hours (healthy)
ninf-authentik-worker	ghcr.io/goauthentik/server:2026.5.6	Up 17 hours (healthy)
ninf-caddy	caddy:2-alpine	Up 17 hours
ninf-evolution	evoapicloud/evolution-api:latest	Up 17 hours
ninf-evolution-manager	evoapicloud/evolution-manager:latest	Up 17 hours
ninf-frontend	604e9b9e764f	Up 17 hours
ninf-glpi	elestio/glpi:latest	Up 19 minutes
ninf-glpi-db	mariadb:10.11	Up 17 hours
ninf-n8n	docker.n8n.io/n8nio/n8n:latest	Up 19 minutes
ninf-postgres	timescale/timescaledb:latest-pg16	Up 17 hours (healthy)
ninf-redis	redis:7-alpine	Up 17 hours (healthy)
ninf-worker-alerts	31a99dc9460e	Up 15 minutes (healthy)
ninf-worker-ml	31a99dc9460e	Up 15 minutes (healthy)
```

### zbx-prd-01 (Ubuntu 24.04.4 LTS)

Coletado em 2026-10-27 08:45 -03.

#### Sistema

```
kernel 6.8.0-147-generic
cpu 12 vCPU
Mem: 47Gi usado 17Gi
Swap: 8.0Gi usado 0B
America/Sao_Paulo yes
```

#### Disco

```
Filesystem     Type  Size  Used Avail Use% Mounted on
/dev/sda1      ext4  387G  158G  229G  41% /
/dev/sda16     ext4  881M  117M  703M  15% /boot
/dev/sda15     vfat  105M  6.2M   99M   6% /boot/efi
```

#### Serviços (ativos e habilitados)

```
ssh                active    disabled
ufw                active    enabled
fail2ban           active    enabled
systemd-timesyncd  active    enabled
mariadb            active    enabled
mysql              active    alias
zabbix-server      inactive  masked
zabbix-agent2      active    enabled
```

#### Timers

```
apport-autoreport.timer apport-autoreport.service
apt-daily-upgrade.timer apt-daily-upgrade.service
apt-daily.timer apt-daily.service
certbot.timer certbot.service
dpkg-db-backup.timer dpkg-db-backup.service
e2scrub_all.timer e2scrub_all.service
fstrim.timer fstrim.service
fwupd-refresh.timer fwupd-refresh.service
logrotate.timer logrotate.service
man-db.timer man-db.service
motd-news.timer motd-news.service
ness-zabbix-backup.timer ness-zabbix-backup.service
ness-zabbix-object-storage-backup.timer ness-zabbix-object-storage-backup.service
phpsessionclean.timer phpsessionclean.service
snapd.snap-repair.timer snapd.snap-repair.service
sysstat-collect.timer sysstat-collect.service
sysstat-summary.timer sysstat-summary.service
systemd-tmpfiles-clean.timer systemd-tmpfiles-clean.service
ua-timer.timer ua-timer.service
update-notifier-download.timer update-notifier-download.service
update-notifier-motd.timer update-notifier-motd.service
```

#### Portas em escuta (fora de loopback)

```
22 0.0.0.0 sshd
10050 * zabbix_agent2
```

#### UFW

```
Status: active
22/tcp                     ALLOW       Anywhere                   # SSH key-only bootstrap
443/tcp                    ALLOW       173.245.48.0/20            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       103.21.244.0/22            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       103.22.200.0/22            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       103.31.4.0/22              # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       141.101.64.0/18            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       108.162.192.0/18           # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       190.93.240.0/20            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       188.114.96.0/20            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       197.234.240.0/22           # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       198.41.128.0/17            # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       162.158.0.0/15             # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       104.16.0.0/13              # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       104.24.0.0/14              # Cloudflare to Zabbix UAT
443/tcp                    ALLOW       172.64.0.0/13              # Cloudflare to Zabbix UAT
10051/tcp                  ALLOW       131.255.253.131            # Zabbix active proxy allowlist
10051/tcp                  ALLOW       131.255.82.236             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       170.254.14.18              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       177.200.83.84              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       177.36.37.242              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       179.228.138.35             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       186.215.152.18             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       186.216.160.139            # Zabbix active proxy allowlist
10051/tcp                  ALLOW       186.31.28.250              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       187.102.187.22             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       187.72.166.146             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       187.92.158.195             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       190.81.54.122              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       191.202.8.222              # Zabbix active proxy allowlist
10051/tcp                  ALLOW       191.241.243.241            # Zabbix active proxy allowlist
10051/tcp                  ALLOW       200.143.94.229             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       200.205.13.130             # Zabbix active proxy allowlist
10051/tcp                  ALLOW       85.209.93.35               # Zabbix active proxy allowlist
80/tcp                     ALLOW       Anywhere                   # Zabbix production ACME and HTTPS redirect
443/tcp                    ALLOW       Anywhere                   # Zabbix production HTTPS
10051/tcp                  ALLOW       144.91.72.202              # Zabbix cutover bridge temporary
22/tcp (v6)                ALLOW       Anywhere (v6)              # SSH key-only bootstrap
80/tcp (v6)                ALLOW       Anywhere (v6)              # Zabbix production ACME and HTTPS redirect
443/tcp (v6)               ALLOW       Anywhere (v6)              # Zabbix production HTTPS
```

