# Ansible `common` — `--check --diff` nos três hosts (Task 1.2 Step 5)

27/10/2026, só leitura (`--check`), chave `nessos_agent`. **Nada aplicado.**

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
| `admin_ssh_key` antiga | Variável e task removidas (a chave do agente já está nos hosts) |
| `/etc/sudoers.d/ness_admin` duplicado | `sudoers_file` gerencia o arquivo existente (`90-ness_admin` por padrão e na UAT; `90-ness-admin` na AIOps; `ness_admin` no prod), com `validate: visudo -cf` |

## Re-check `--check --diff` (27/10/2026, nada aplicado)

`rc=0`; `changed` aiops-01=10, zabbix-prod=6, zabbix-uat=10. Diff residual:

| Tarefa | Hosts | Observação |
|---|---|---|
| UFW | nenhum | Nenhuma regra aberta, removida ou re-comentada |
| `authorized_key` | nenhum | — |
| sudoers | zabbix-prod | `(ALL)` → `(ALL:ALL)`: equivalente, mesmo arquivo; nenhum arquivo novo |
| `/etc/hosts` `127.0.1.1` | aiops-01, zabbix-uat | Tira o FQDN `*.contaboserver.net`; inofensivo |
| `fail2ban` `jail.local` novo | os três | **Ainda a revisar** (muda bantime/jails ativos) |
| Drop-in `zz-ness-baseline.conf` | os três | Efetivo já é `password no`, `kbd no`; esperado |
| sysctl | aiops-01, zabbix-uat (+ `tcp_max_syn_backlog` nos três) | Tuning do kernel; aceitar só com valores revisados |
| Pacotes básicos / cache APT | aiops-01, zabbix-uat | Inofensivo |

Restam antes do `apply`: revisar o template do fail2ban e os valores de sysctl.
