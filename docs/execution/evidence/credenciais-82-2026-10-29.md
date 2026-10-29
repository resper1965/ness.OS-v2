# Issue #82 — conferência de credenciais expostas (29/10/2026)

Sem valores, hashes ou trechos de segredo neste documento. Escopo: o que o histórico do
GitHub ainda expõe e se cada valor ainda funciona.

## Método
- Clone `--mirror` do remoto (inclui `refs/pull/*`) e `gitleaks` 8.30.1 (versão do CI) com
  `.gitleaks.toml` e `.gitleaksignore` da `main`, `--log-opts=--all`.
- Cada valor achado foi testado só por leitura, a partir do arquivo temporário (apagado
  com `shred`): `rclone lsd`, `crypt` contra `/etc/shadow`, `mariadb -e "select 1"` e
  `host.get` na API do Zabbix. Nada foi alterado nos servidores.

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
| Senha de SSH da aiops (`run_provision_sso.py`; 2 valores) | 7 commits em heads e PR 41 | **Achado novo**, o gitleaks não pega. Não vale para `root` na aiops nem no Zabbix prod, nem para o `root` do MariaDB do GLPI. SSH por senha desligado nos dois hosts. |
| `escalate-incident.yml` (2 achados) | refs de PR | Falso positivo: URL interna sem segredo. |

## GLPI (produção)
- Senhas de fábrica de `glpi`, `post-only`, `tech`, `normal`: **não valem**.
- 43 contas locais legadas ativas (ids 7–57; `authtype` 0/1), quase todas sem login, com
  senha local, e duplicadas por contas SSO (`authtype` 3, ids 59–79 e seguintes). Não há
  evidência de uso; a política de senha dessas contas não foi verificada.

## Não verificado
- UAT (`169.58.234.9`) e a `homol` do Wazuh contra as senhas de SSH antigas.
- Outros segredos que não tenham formato que o gitleaks reconheça.
- Se o pedido ao GitHub Support foi aberto e atendido (a #82 não registra o número).
