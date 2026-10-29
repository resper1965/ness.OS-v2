# Issue #82 — conferência de credenciais expostas (29/10/2026)

Sem valores, hashes ou trechos de segredo neste documento. Escopo: o que o histórico do
GitHub ainda expõe e se cada valor ainda funciona.

## Método
- Clone `--mirror` do remoto (inclui `refs/pull/*`) e `gitleaks` 8.30.1 (versão do CI) com
  `.gitleaks.toml` e `.gitleaksignore` da `main`, `--log-opts=--all`.
- Cada valor achado foi testado só por leitura, a partir do arquivo temporário (apagado
  com `shred`): `rclone lsd`, `crypt` contra `/etc/shadow`, `mariadb -e "select 1"` e
  `host.get` na API do Zabbix. Nada foi alterado nos servidores.
- "Recusada" vale só para os valores achados no histórico e só no teste de 29/10; não prova que o
  segredo atual seja outro nem que esteja revogado em outros hosts.

## Estado do remoto
- Repositório **público** hoje (janela do Actions; zero forks). 75 heads, 1 tag, 110 refs de PR.
- Heads e tag: o scan com o `.gitleaksignore` atual passa. Os 7 achados restantes
  estão **só em `refs/pull/*`** (4 commits anteriores à reescrita de 13/10), o que confirma
  que o pedido de limpeza dos refs de PR ao GitHub Support continua necessário.

## Achados e resultado
| Item | Onde | Resultado |
|---|---|---|
| `mariadb_root_password` (inventário Ansible) | 25 refs de PR | Recusada no MariaDB do Zabbix prod. |
| `backup_s3_secret_key` (idem) | 25 refs de PR | Recusada pelo Contabo (`SignatureDoesNotMatch`). Access ID difere do atual. |
| Token da API do Zabbix (`get_zabbix_users.py`, `secops.py`, `reconnect-proxies.yml`; 1 valor, 3 commits) | refs de PR | **Achado novo**, não estava na #82. Recusado (`Not authorized`) em `zabbix.ness.com.br`. |
| Senha de SSH da aiops (`run_provision_sso.py`; 2 valores) | 7 commits em heads e PR 41 | **Achado novo**, o gitleaks não pega. Recusada para `root` na aiops e no Zabbix prod e para o `root` do MariaDB do GLPI (só os 2 valores achados). SSH por senha desligado nos dois hosts. |
| `escalate-incident.yml` (2 achados) | refs de PR | Falso positivo: URL interna sem segredo. |

## GLPI (produção)
- Senhas de fábrica de `glpi`, `post-only`, `tech`, `normal`: recusadas no login de teste (só essas; sem varredura de outras senhas).
- Contas ativas por tipo de autenticação (contagem completa, sem `LIMIT`):
  - 38 locais com senha (17 `authtype` 0, 21 `authtype` 1). Dessas, só 2 já logaram:
    `svc_ness_os` (94, Hub, hoje) e `glpi` (2, 27/07). Nenhuma conta de pessoa.
  - 35 SSO (`authtype` 3) sem senha local, nenhuma com login ainda.
  - 3 sem senha local: `svc_ness_maintenance` (106, 28/10), `glpi-system` e `akadmin` (SSO, 13/10).
- As outras 36 contas locais (33 de pessoas e `post-only`, `tech`, `normal`) nunca logaram;
  as de pessoas duplicam as contas SSO. Candidatas a desativação; **não alterei nada**. A política de senha delas
  não foi verificada.

## Não verificado
- UAT (`169.58.234.9`) e a `homol` do Wazuh contra as senhas de SSH antigas.
- Outros segredos que não tenham formato que o gitleaks reconheça.
- Se o pedido ao GitHub Support foi aberto e atendido (a #82 não registra o número).
