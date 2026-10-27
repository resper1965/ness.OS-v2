# Runbook GLPI — T03: gateway de manutenção em produção (Task 2.3)

Contrato e decisão: [ADR 0020](../../../docs/adr/0020-glpi-maintenance-entity-boundary.md). Host AIOps `144.91.115.242`, comandos com `sudo -n`.
Levantamento de 27/10/2026 (somente leitura); nenhum segredo foi impresso.

## Decisões do Ricardo (27/10)

Backup novo antes de mexer · perfil 13 só com `computer=1` · cliente API novo para o gateway com IP único `172.30.250.3` · GLPI pode cair alguns segundos na recriação do contêiner.

## Achados que mudam o plano

- **Hub (`ninf-api` e `worker-alerts`) usa o cliente API 2 "ness-os-integration"** (faixa 172.18.0.0/16). Comparado dentro dos contêineres por SHA-256 do `NINF_GLPI_APP_TOKEN` contra `glpi_apiclients.app_token` decifrado: ambos casam só com o 2. O `n8n` não tem a variável.
- **O cliente 1 "Ness AIOps Integration" é o buraco.** Está ativo, sem faixa de IP, e o `app_token` gravado não decifra (formato legado, não é sodium). O GLPI 11 (`API.php`) então o guarda como token `''`, e `checkAppToken()` aceita **initSession sem o cabeçalho `App-Token`**: de `ninf-api` sem App-Token o GLPI chega a validar o `user_token` (401 `ERROR_GLPI_LOGIN_USER_TOKEN`, não 400). Resultado: a credencial da 106 funcionaria a partir do Hub, sem App-Token, de qualquer IP.
- **Restringir o cliente 1 a 172.18.0.0/16 não resolve**: o Hub está nessa faixa e continuaria entrando sem App-Token. **Recomendo desativar o cliente 1** (`client --id=1 --deactivate`). Nada no repositório o usa (Hub e workers usam o 2; n8n cai em `'glpi-app-token'`, que já dá 400). Antes de desativar, confirmar nos logs das últimas 24 h que não há `initSession` sem App-Token de outra origem (Zabbix, scripts). Rollback: `client --id=1 --activate`.
- O `glpi_network_boundary_probe.py` sempre dá `BLOCKED_DIRECT_PATH` (`ninf-glpi` segue na `ninf-net` por causa do Hub). O critério de aceite da fronteira é a **sonda funcional** abaixo.
- `ness-aiops-backup.service` **para o `ninf-glpi`** durante o `tar` do volume (visto: contêiner `Exited (137)` por ~1–2 min). É a queda "de alguns segundos" aceita; o backup novo tem o mesmo efeito.

## Ferramentas (repo)

| Arquivo | Função |
|---|---|
| `infra/scripts/glpi-maintenance-admin.php` | `apiclient`, `profile`, `rotate`, `user`, `client`. Lê do `stdin`, roda no contêiner GLPI. |
| `infra/scripts/glpi_t03_functional_probe.py` | Sonda funcional (stdlib). |
| `infra/scripts/glpi_maintenance_preflight.py` | Guard local de imagem, sub-rede, IP e segredos. |
| `infra/tests/test_glpi_t03_prod_tooling.py` | Testes (fakes + lab). |

Uso do PHP (sempre `-u www-data`; `--` antes dos argumentos):

```bash
A='sudo -n docker exec -i -u www-data ninf-glpi php --'
$A apiclient            < glpi-maintenance-admin.php   # dry-run
$A apiclient --apply    < glpi-maintenance-admin.php > $S/app_token   # umask 077; token só no stdout
$A profile  [--apply]   < ...      # perfil 13 -> computer=1
$A rotate   --apply     < ... > $S/user_token
$A user     --activate|--deactivate < ...
$A client   --id=1 --deactivate|--activate < ...
```

Defaults de produção: usuário 106 `svc_ness_maintenance`, perfil 13 `ness-maintenance-alupar`, cliente `ness-os-maintenance-gateway`, IP `172.30.250.3`. Id e nome precisam bater, senão aborta (`--user= --user-name= --profile= --profile-name= --client-name= --ip=` para o lab). Segredo só no stdout; estado e readback em JSON no stderr. Idempotente: repetir não muda nada nem reescreve o token (use `--reset-token` para trocar o App-Token).

Variáveis comuns:

```bash
IMG=ghcr.io/resper1965/ninf-api@sha256:31a99dc9460ec31dd7a830c480c8f48b76f68946ebc17d065fc9654a835dc8ec  # conferir: é o digest em execução
A=/opt/n-infraops/app
S=/etc/ness-os/glpi-maintenance
RB=/opt/n-infraops/rollback/glpi-t03-prod-$(date +%Y%m%d)
```

## Passos

### 1. Backup novo e baseline (sem mudança)

```bash
sudo -n install -d -m 0700 $RB
sudo -n systemctl start ness-aiops-backup.service       # ~8 min; GLPI cai durante o tar do volume
d=$(sudo -n sh -c 'ls -d /opt/n-infraops/backups/nightly/*/ | tail -1')
sudo -n test -e $d/COMPLETED && sudo -n sh -c "cd $d && sha256sum -c SHA256SUMS | grep -vc ': OK'"   # esperado 0
sudo -n docker inspect ninf-glpi ninf-api ninf-worker-alerts --format '{{.Name}} {{.Image}} {{json .NetworkSettings.Networks}}' | sudo -n tee $RB/inspect-before.txt >/dev/null
sudo -n cp -a $A/docker-compose.tickets.yml $A/docker-compose.yml $RB/
sudo -n docker exec ninf-glpi-db sh -c 'mariadb -uroot -p"${MARIADB_ROOT_PASSWORD:-$MYSQL_ROOT_PASSWORD}" glpi -t -e "SELECT id,name,is_active,ipv4_range_start,ipv4_range_end FROM glpi_apiclients; SELECT id,is_active FROM glpi_users WHERE id IN (94,106); SELECT name,rights FROM glpi_profilerights WHERE profiles_id=13 AND rights>0"' | sudo -n tee $RB/db-before.txt
```

Verificação: backup novo `COMPLETED`, contagem de falhas `0`, `ninf-glpi` voltou `Up`, Hub com 200. Rollback: n/a.

### 2. Segredos do gateway e preflight

```bash
sudo -n install -d -m 0700 -o root -g root $S
sudo -n sh -c "umask 077; openssl rand -hex 32 | tr -d '\n' > $S/bearer; test -s $S/user_token || printf pendente > $S/user_token"
sudo -n stat -c '%A %U:%G %s %n' $S/*
```

O `app_token` nasce no passo 4. Preflight (`glpi_maintenance_preflight.py`) só depois dele: `PASS_LOCAL_PREFLIGHT`.
Verificação: `-rw------- root:root`. Rollback: `sudo -n rm -rf $S`.

### 3. Override no host

Copiar `app/docker-compose.glpi-maintenance.yml` para `$A/` e conferir o `sha256sum` com o do repositório. Colisão: `docker network inspect` de todas as redes e `ip route` sem `172.30.250.` (esperado 0; levantamento: livre). Rollback: `sudo -n rm $A/docker-compose.glpi-maintenance.yml`.

### 4. Cliente API do gateway e perfil 13

Copiar `glpi-maintenance-admin.php` para `$RB/`.

```bash
P="sudo -n docker exec -i -u www-data ninf-glpi php --"
$P apiclient < $RB/glpi-maintenance-admin.php                              # dry-run: action create
sudo -n sh -c "umask 077; $P apiclient --apply < $RB/glpi-maintenance-admin.php > $S/app_token"
sudo -n test -s $S/app_token && sudo -n stat -c '%a %s' $S/app_token       # 600 40
$P profile --apply < $RB/glpi-maintenance-admin.php                        # {"after":{"computer":1}}
```

Verificação: stderr mostra `172.30.250.3-172.30.250.3`; repetir o `--apply` dá `action:none` e não toca o arquivo (o `>` esvaziaria, então **não repita com redirecionamento**; repita sem). Clientes 1 e 2 inalterados. Depois rodar o preflight (`PASS_LOCAL_PREFLIGHT`).
Rollback: `$P client --id=<novo> --deactivate`; perfil 13: `UPDATE glpi_profilerights SET rights=13 WHERE profiles_id=13 AND name='computer'` (valor antigo em `$RB/db-before.txt`).

### 5. Subir gateway e ligar o GLPI à rede privada

```bash
cd $A
export NINF_API_IMAGE=$IMG NESS_GLPI_MAINTENANCE_SUBNET=172.30.250.0/28 NESS_GLPI_MAINTENANCE_GATEWAY_IP=172.30.250.3 \
  NESS_GLPI_MAINTENANCE_APP_TOKEN_FILE=$S/app_token NESS_GLPI_MAINTENANCE_USER_TOKEN_FILE=$S/user_token NESS_GLPI_MAINTENANCE_BEARER_FILE=$S/bearer \
  NESS_GLPI_MAINTENANCE_APPROVED_IDS=<ID_ENTIDADE_1>
F="-p app -f docker-compose.tickets.yml -f docker-compose.glpi-maintenance.yml"
sudo -n -E docker compose $F config --quiet && echo CONFIG_OK
sudo -n -E docker compose $F up -d --no-deps glpi glpi-maintenance-gateway      # recria ninf-glpi (segundos fora)
sudo -n docker inspect ninf-glpi-maintenance-gateway --format '{{.State.Health.Status}} {{.Config.Image}} {{json .HostConfig.PortBindings}}'
sudo -n docker inspect ninf-api ninf-worker-alerts --format '{{.Name}} {{range $k,$v:=.NetworkSettings.Networks}}{{$k}} {{end}}'
```

Verificação: `CONFIG_OK`; gateway `healthy`, digest = `$IMG`, `PortBindings {}`; Hub e worker continuam só em `app_ninf-net`; UI pública 302, Hub 200, logs do GLPI sem 4xx novos dos 172.18.0.4/11.
Rollback: `sudo -n docker compose -p app -f docker-compose.tickets.yml up -d --no-deps glpi`; `docker compose $F rm -sf glpi-maintenance-gateway`; `docker network rm app_glpi-maintenance-private`.

### 6. Fechar o cliente 1 e rotacionar o token da 106 (106 ainda inativa)

```bash
$P client --id=1 --deactivate < $RB/glpi-maintenance-admin.php
sudo -n sh -c "umask 077; $P rotate --apply < $RB/glpi-maintenance-admin.php > $S/user_token.new && test -s $S/user_token.new && mv $S/user_token.new $S/user_token"
sudo -n stat -c '%a %U %s' $S/user_token                       # 600 root 40
sudo -n docker restart ninf-glpi-maintenance-gateway           # lê o segredo só no start
sudo -n docker inspect ninf-glpi-maintenance-gateway --format '{{.State.Health.Status}}'
```

Verificação: Hub segue 200 pelo cliente 2 (`docker logs --since 2m ninf-glpi` sem `ERROR_WRONG_APP_TOKEN` novo); gateway `healthy`. Se o Hub quebrar: reativar o 1 (rollback) e investigar quem o usava.
Rollback: `client --id=1 --activate`. O token antigo da 106 morre na rotação; sem o que restaurar (conta inativa).

### 7. Ativar a 106 e provar a fronteira (mesma janela; desativa se falhar)

A sonda precisa da 106 **ativa**: inativa, o GLPI recusa de qualquer forma e o resultado não prova nada.

```bash
$P user --activate < $RB/glpi-maintenance-admin.php
sudo -n python3 infra/scripts/glpi_t03_functional_probe.py --docker "docker" --skip-env-token \
  --allowed-id <ID_ENTIDADE_1> --denied-id <ID_FILHA> <ID_INEXISTENTE>
echo rc=$?
```

**Esperado: a linha do `container-env` FALHA** (`initSession ... container-env -> 200`) nos dois contêineres. O Hub tem o App-Token do cliente 2, válido a partir do IP dele, e o GLPI valida só App-Token + `user_token`: quem juntar o `user_token` da 106 com o token do Hub entra. O lab (App-Token só do gateway) não mostrava isso. A fronteira real é, portanto, o **sigilo do `user_token`** (arquivo 0600 root + gateway) + a checagem de entidade do gateway; o Hub não tem o `user_token`. Para aceitar o risco explicitamente, rodar com `--skip-env-token`: então esperado `PASS_FUNCTIONAL_PROBE`, rc 0, e registrar o risco aceito no ADR 0020. Sem `--skip-env-token` o rc é 1 por desenho, e a decisão fica com o Ricardo. A sonda prova, de dentro de `ninf-api` e `worker-alerts`: `initSession` com o `user_token` da 106 é recusado (400/401/403) com (a) nenhum App-Token, (b) o App-Token do gateway, (c) o `NINF_GLPI_APP_TOKEN` do próprio contêiner (omitido com `--skip-env-token`); e que o gateway devolve 200 só para o ID permitido (corpo `{id,name,entities_id=1}`), 404 para os demais, com query string, sem bearer (401) e POST. Os tokens vão por `stdin`, nunca por argv ou saída.
Se `FAIL`: `$P user --deactivate < ...` imediatamente e reverter os passos 6 e 5.
Rota pública: `/apirest.php` e `/apirest%252Ephp/initSession` → 403.
Verificação final: `user` mostra um único vínculo `[13, 1, 0]` (perfil 13, entidade 1, não recursivo). Rollback: `user --deactivate`.

### 8. Evidência

Salvar em `docs/execution/evidence/` (sem token): digest, hashes do override, saída das sondas, readbacks JSON, backup usado. Atualizar ADR 0020, issue #74, T03/G2 e indicador F3.

## Rollback total (ordem)

1. `user --deactivate` (106). 2. `docker compose $F rm -sf glpi-maintenance-gateway`. 3. `docker compose -p app -f docker-compose.tickets.yml up -d --no-deps glpi`. 4. `docker network rm app_glpi-maintenance-private`. 5. `client --id=<novo> --deactivate`; `client --id=1 --activate` se necessário; `rm -rf $S`. 6. Hub 94 nunca saiu do cliente 2: nada a restaurar.

## Rotação periódica do token da 106

`rotate --apply` para o arquivo (como no passo 6) + `docker restart ninf-glpi-maintenance-gateway` + sonda. Nunca `cat` nos arquivos de segredo.

## Pendências e riscos

- Confirmar ID da entidade 1 permitido (1–5) e um ID de entidade filha só para o teste negativo.
- Consumidor do bearer do gateway ainda não definido (P3).
- Sem filtro de rede: a fronteira é IP do cliente + sigilo do `user_token` + checagem de entidade do gateway.
- **Risco principal:** o cliente 2 (App-Token do Hub, 172.18/16) aceita o `user_token` da 106 a partir do Hub. O filtro de IP do cliente 3 só impede o App-Token do gateway de ser usado de fora; não impede o do Hub. Mitigação possível (decisão): conta 94/Hub com App-Token distinto não resolve; só tirar o Hub do IP/rede do GLPI ou aceitar o risco com o `user_token` confinado.
