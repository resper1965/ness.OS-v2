# Ansible `common` — `--check --diff` nos três hosts (Task 1.2 Step 5)

27/10/2026, chave `nessos_agent`. As seções até "Apply" são `--check` (só leitura); o apply está na seção "Apply", no fim.

## Correções para o `--check` rodar

| Problema | Correção |
|---|---|
| `stdout_callback = yaml` removido do `community.general` 12 | `default` + `result_format = yaml` |
| `sshd -t`/`-T` pulados em `--check` → asserção falhava e o rescue disparava | `check_mode: false` (só leitura) |
| `zabbix-uat` é Ubuntu 24.04; a asserção exigia Debian 12 | aceita Debian 12 ou Ubuntu 24.04 |
| `apt upgrade: dist` atualizaria `docker-ce` na AIOps (reinicia todos os containers) e faria `autoremove` de plugins MariaDB no `zabbix-prod` | desligado por padrão (`common_full_upgrade: true` para ligar) |

Resultado: `rc=0`; `changed` aiops-01=15, zabbix-prod=5, zabbix-uat=15.

## Bloqueios resolvidos (PR `fix/common-apply-ready`)

| Bloqueio | Correção |
|---|---|
| UFW 80/443/10051 de qualquer origem | Lista `ufw_allow` por host em `hosts.yml` (padrão: só SSH). Modela só o que já existe: prod 80/443/10051; UAT 80/443 e 10051 de 144.91.72.202; AIOps 80/443. Faixas Cloudflare e allowlist de proxies da UAT ficam fora da role e não são tocadas |
| `admin_ssh_key` antiga (`cursor-agent-stackvps`) | Trocada pela chave atual do agente, já presente nos 3 hosts (`ok`, sem diff); garante acesso em VPS nova após `AllowUsers` |
| `/etc/sudoers.d/ness_admin` duplicado | `sudoers_file` gerencia o arquivo existente (`90-ness_admin` por padrão e na UAT; `90-ness-admin` na AIOps; `ness_admin` no prod), com `validate: visudo -cf` |

## Re-check `--check --diff` (27/10/2026, nada aplicado)

`rc=0`; `changed` aiops-01=10, zabbix-prod=6, zabbix-uat=10 (após ajustes da revisão: `ssh_allow_users`, `fail2ban_ignoreip`). Diff residual:

| Tarefa | Hosts | Observação |
|---|---|---|
| UFW | nenhum | Nenhuma regra aberta, removida ou re-comentada |
| `authorized_key` | nenhum | — |
| sudoers | zabbix-prod | `(ALL)` → `(ALL:ALL)`: equivalente, mesmo arquivo; nenhum arquivo novo |
| `/etc/hosts` `127.0.1.1` | aiops-01, zabbix-uat | Tira o FQDN `*.contaboserver.net`; inofensivo |
| `fail2ban` `jail.local` novo | os três | Com `ignoreip` (localhost, stack, aiops, zabbix-prod). Em aiops-01 e UAT, `jail.d/*.local` (`maxretry = 5`, `bantime = 1h`) sobrepõe o `jail.local`, então o efetivo não muda lá |
| Drop-in `zz-ness-baseline.conf` | os três | Efetivo já é `password no`, `kbd no`; `AllowUsers ness_admin` (aiops-01: `ness_admin root`, ver abaixo) |
| sysctl | aiops-01, zabbix-uat (+ `tcp_max_syn_backlog` nos três) | Tuning do kernel; aceitar só com valores revisados |
| Pacotes básicos / cache APT | aiops-01, zabbix-uat | Inofensivo |

Revisados antes do `apply` (revisor do #106): fail2ban com `ignoreip`; sysctl só aumenta valores.

## Ajustes da revisão

- `AllowUsers` vem de `ssh_allow_users` (padrão `[admin_user]`). Em aiops-01 é `[ness_admin, root]`: root loga lá por chave e remover root depende do OK do Ricardo. O assert checa que `sshd -T` `allowusers` é exatamente `ssh_allow_users` (fora do `--check`, pois o template não é escrito).
- `fail2ban_ignoreip` em `group_vars/all.yml`, aplicado no `[DEFAULT]`.
- Teste: sudoers pré-existente `(ALL)` vira `(ALL:ALL)` no mesmo arquivo e passa no `visudo -c`; `allowusers ness_admin` verificado.

## Ordem do apply

UAT → aiops-01 → zabbix-prod (produção por último), um host por vez, com uma **segunda sessão SSH aberta** durante o apply e `sshd -T`/login testado em nova sessão antes de seguir ao próximo. `common_full_upgrade` continua desligado.

## Apply (27/10, GO do Ricardo)

Ordem UAT → aiops → prod, cada um com sessão SSH de reserva aberta.

| Host | Resultado | Verificação pós-apply |
|---|---|---|
| zabbix-uat | 1ª tentativa: assert de `allowusers` falhou (linha duplicada no `sshd -T`, ver #108); rescue reverteu o drop-in, sshd não recarregado, acesso intacto. 2ª (com #108): rc=0, changed=7 | sessão nova ok; `allowusers ness_admin`, `maxauthtries 3`; fail2ban `sshd` ativo; `zabbix-server` já estava `masked` antes (não é efeito do apply) |
| aiops-01 | rc=0, changed=12 | `allowusers ness_admin root`; `ignoreip` com stack/hub/zabbix; todos os contêineres Up; API/worker/postgres healthy; worker sem `raised unexpected`; `https://hub.ness.com.br/api/assets` → 401 |
| zabbix-prod | rc=0, changed=6 | `port 2222`, `allowusers ness_admin`; `visudo -c` ok; zabbix-server/mariadb/apache2/fail2ban active; `https://zabbix.ness.com.br/` → 200 |

Idempotência: `--check --diff` logo após → `changed=0` nos três.

### Root sem SSH na aiops-01 (27/10, OK do Ricardo)

Logins de root nos últimos 14 dias vieram só de duas chaves (`cursor-agent-stackvps` e a do agente), ambas também em `ness_admin`. `ssh_allow_users` volta ao padrão: apply rc=0, changed=2 (drop-in + reload); `allowusers ness_admin`; `root@` → `Permission denied (publickey)`; `ness_admin` + sudo ok.
