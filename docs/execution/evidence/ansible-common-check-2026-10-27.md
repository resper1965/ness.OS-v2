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

## Diferenças restantes — **bloqueiam `apply`**

| Tarefa | Hosts | Efeito se aplicado | Decisão |
|---|---|---|---|
| UFW permite 80/443/10051 de qualquer origem | aiops-01, zabbix-uat | Na UAT anula a restrição de 443 à Cloudflare; abre 10051 na AIOps sem uso | Regras por host antes de aplicar |
| `authorized_key` com `admin_ssh_key` (`cursor-agent-stackvps`) | zabbix-uat | Adiciona chave antiga que hoje não está lá | Remover essa chave do `group_vars` |
| `/etc/sudoers.d/ness_admin` | aiops-01, zabbix-uat | Duplica `90-ness_admin` já existente | Reusar o arquivo existente |
| `/etc/hosts` `127.0.1.1` | aiops-01, zabbix-uat | Tira o FQDN `*.contaboserver.net` | Inofensivo; aceitar |
| `fail2ban` `jail.local` novo | os três | Muda bantime/jails ativos | Revisar o template antes |
| Drop-in `zz-ness-baseline.conf` | os três | Efetivo já é `password no`, `kbd no`; porta igual | Esperado |
| sysctl (`somaxconn`, `tcp_max_syn_backlog`, `swappiness`) | variado | Tuning do kernel em produção | Aceitar só com valores revisados |
| Pacotes básicos | zabbix-uat | 7 pacotes novos | Inofensivo |
| UFW porta SSH | os três | Só o comentário da regra já existente (o nome "2222" no log vem do 1º host; AIOps/UAT usam 22) | Inofensivo |

Estado efetivo do SSH hoje (`sshd -T`): os três com `passwordauthentication no`, `kbdinteractiveauthentication no`; AIOps `permitrootlogin without-password`.
