# Roteiro da janela: cutover do Zabbix para a VPS nova

**Quando:** sábado 14/11/2026, início 23:00, **teto 02:00** (se a VPS nova não estiver no ar até lá, volta para a origem).
**Quem opera:** o agente executa os passos; o Ricardo fica de plantão e decide o rollback.
**Plano de referência:** `docs/superpowers/plans/2026-11-06-zabbix-cutover-acesso-cloudflare.md` (Tasks 6 a 9).
**Duração estimada:** ~2 h (dump 32 min + envio 15 min + restore 58 min + religar e conferir 15 min).

Nomes: **origem** = `zabbix-srv01` (`144.91.72.202`, ssh `-p 2222`); **destino** = `ness-os-zbx-prd-01` (`169.58.234.9`).
Nenhum comando abaixo contém segredo. Segredos ficam em `/etc/ness-os` (destino) e `~/.local/zbx` (stack).

---

## Antes: sexta 13/11 (sem janela, mas tudo precisa estar OK)

Se qualquer item falhar, **o corte não acontece** e a nova data é combinada.

| # | Verificação | Como | Esperado |
|---|---|---|---|
| A1 | Buffer dos proxies | saídas do script `zabbix-proxy-set-offline-buffer.sh` do Ismael, 18 proxies | `ProxyOfflineBuffer=24` em todos (mínimo aceito: 3 h) |
| A2 | Proxies reportando | `proxy.get` pela API, `lastaccess` | 18 de 18 frescos, sem contar o `stacavprx` (19ª linha, parado desde 11/09) |
| A3 | Dump noturno da origem | `ls /var/backups/zabbix/nightly` | dump de 13/11 22:00 com `COMPLETED` (é só reserva; o dump do corte é novo) |
| A4 | Disco | origem e destino | origem > 100 GB livres; destino > 80 GB livres (hoje 158 GB) |
| A5 | Scripts novos | **destino:** `ness-zabbix-cutover-enable-production` (#218) e `ness-zabbix-saml-entra-apply` (#223, já instalado). **Origem:** `zabbix-cutover-backup` (#219) copiado para `/usr/local/sbin` (hoje não está lá). | versão da `main`, modo 755 root |
| A6 | Teste de acesso | 2 técnicos entram pelo M365 em `zabbix-web.ness.com.br`, um fora da rede; e-mail externo barrado | OK |
| A7 | Senha do `akadmin` | `ZBX_BREAKGLASS_AKADMIN_PASSWORD` gravada no `projetos.env` pelo Ricardo | OK |
| A7b | Sessão do `akadmin` no destino | `sessions` por usuário | **0 sessões em 12/11** (a aberta desde 10/11 foi encerrada com autorização) | OK |
| A8 | **Firewall do destino (correção)** | `ufw status` no destino | **sem 80/443 para Anywhere** (hoje existem 4 regras: 80 e 443, v4 e v6; remover antes) |
| A9 | Hub pronto | `.env` da aiops com `NINF_ZABBIX_ACCESS_CLIENT_ID/SECRET` **não** gravado ainda; backup do `.env` feito | grava-se no Passo 8 |
| A10 | Aviso aos técnicos | mensagem enviada: Zabbix só entra pelo M365; usuário = e-mail completo; janela de coleta parada | enviado |

**Nota de DNS:** `zabbix.ness.com.br` hoje é registro A sem proxy, TTL automático. O script mantém TTL e proxy; só troca o IP. Reduzir o TTL 24 h antes (Task 6, Step 1) só se o Ricardo der a frase da Task 6.

**A8 em detalhe:** a VPS nova tem 80/443 abertos para qualquer origem (regras "Zabbix production ACME and HTTPS redirect" e "Zabbix production HTTPS", v4 e v6). Isso expõe o Zabbix diretamente, e o `ness-zabbix-cutover-enable-production` aborta com essas regras. Antes do corte: `ufw delete` de cada uma (por número, conferindo), mantendo o 443 só para as faixas da Cloudflare, se ainda forem úteis, e mantendo a 10051 só para a allowlist dos proxies. O acesso pelo túnel não usa 80/443.

---

## Janela: sábado 14/11

Anote a hora de cada passo no registro `docs/execution/zabbix-cutover-2026-11.md` (criar na execução).

### Passo 0: 22:30 Preparação (sem impacto)
- Congelar mudanças no Zabbix (aviso aos técnicos).
- Medir antes: `proxy.get` (todos frescos), contagem de hosts e itens na origem, fila dos proxies.
- Confirmar que o Ricardo está de plantão e a hora-limite do rollback (**02:00**).

### Passo 1: 23:00 Parar a coleta na origem
Começa aqui o relógio do buffer dos proxies.
```
ssh -p 2222 ness_admin@144.91.72.202 'sudo systemctl stop zabbix-server'
```
Conferir `inactive`. `mariadb` e `apache2` continuam. Os proxies começam a guardar dados localmente (buffer de 24 h).

### Passo 2: 23:02 Dump final na origem (~32 min)
```
ssh -p 2222 ness_admin@144.91.72.202 'sudo /usr/local/sbin/zabbix-cutover-backup'   # instalado na origem no A5
```
O script recusa rodar com o `zabbix-server` ativo. Gera `/var/backups/zabbix/cutover/<stamp>` com `SHA256SUMS`. Anotar o `<stamp>`.

### Passo 3: ~23:35 Enviar o dump à VPS nova (~15 min)
Por pipe SSH direto, **sem restic**:
```
ssh -p 2222 ness_admin@144.91.72.202 'sudo cat /var/backups/zabbix/cutover/<stamp>/<arquivo>.sql.gz' \
  | ssh ness_admin@169.58.234.9 'sudo tee /var/lib/ness-os/restore-input/<dir>/dbzabbix.sql.gz >/dev/null'
```
Conferir o SHA-256 contra o `SHA256SUMS` da origem e `gzip -t` no destino. **Hash diferente = abortar e voltar à origem (Passo R).**

### Passo 4: ~23:50 Restore no destino (~58 min)
```
ssh ness_admin@169.58.234.9 'sudo /usr/local/sbin/ness-zabbix-native-restore restore <dump> <sha256>'
```
Esperado: `restore=PASS`, 203 tabelas, `dbversion=7000000`, `active_actions_after=0`, `enabled_media_after=0`, `enabled_connectors_after=0`. Comparar hosts e itens com a medida do Passo 0.

### Passo 5: ~00:50 SAML do Entra (o restore apagou)
```
ssh ness_admin@169.58.234.9 'sudo ness-zabbix-saml-entra-apply'          # simulação: ler o SQL
ssh ness_admin@169.58.234.9 'sudo ness-zabbix-saml-entra-apply --apply'  # aplica
```
Refaz o IdP, o certificado, os usernames com e-mail, o bloqueio da senha local de 14 usuários e a senha do `akadmin`. `resper` e `akadmin` mantêm senha local (quebra de vidro).

O `userdirectoryid=NULL` do `akadmin` é aplicado **sempre**, com ou sem arquivo de senha: sem isso o
restore deixa o `akadmin` preso ao diretório SAML antigo e a senha local é recusada (aconteceu em
10/11).

**Estado em 11/11, conferido:** `/etc/ness-os/zabbix-saml.env` **define**
`AKADMIN_PASS_FILE=/etc/ness-os/akadmin.pass`, mas o arquivo **não existia** no destino. O script
aborta com `sem /etc/ness-os/akadmin.pass` (exit 2), então o **Passo 5 inteiro teria falhado às
00:50**: sem SAML aplicado, sem login, corte perdido.

Corrigido em 11/11, com autorização do Ricardo:

- `/etc/ness-os/akadmin.pass` criado com a senha de quebra de vidro registrada no `projetos.env`,
  modo 600, `root:root`; SHA-256 conferido entre a origem local e o destino.
- Script do #246 instalado no destino (sha256 conferido; backup do anterior em `/root/`).
- Simulação após a correção mostra o `userdirectoryid=NULL` e a troca da senha do `akadmin`.

Para um cutover futuro, o passo é: gravar a senha no arquivo, garantir a linha no
`zabbix-saml.env` e conferir na simulação, antes de qualquer `--apply`.

### Passo 6: ~00:55 Ligar o server no destino (notificações desligadas)
```
ssh ness_admin@169.58.234.9 'sudo ZBX_WEB_EXPOSURE=closed /usr/local/sbin/ness-zabbix-cutover-enable-production'
```
O script aborta se houver 80/443 aberto para Anywhere ou 10051 para Anywhere (por isso o A8). O `ZBX_WEB_EXPOSURE` fica `closed`: a tela só abre pelo túnel.

### Passo 7: ~01:00 DNS e allowlist da 10051
```
# roda onde está o token de DNS (CLOUDFLARE_TOKEN_FILE, modo 600); o script recusa token fora do padrão
cloudflare-zabbix-dns-cutover.sh check
cloudflare-zabbix-dns-cutover.sh cutover      # zabbix.ness.com.br: 144.91.72.202 -> 169.58.234.9 (A, sem proxy, TTL inalterado)
```
- Os proxies resolvem `zabbix.ness.com.br`. Quem ainda apontar para a origem cai na **ponte** (`ness-zabbix-cutover-bridge`, `socat` 10051 → destino), que fica ativa na origem até o último proxy migrar.
- Subir a ponte na origem: `sudo systemctl start ness-zabbix-cutover-bridge` (ela conflita com o `zabbix-server` da origem, que já está parado).
- Allowlist da 10051 no destino: já tem os IPs dos proxies; remover a regra da ponte quando todos migrarem.

### Passo 8: ~01:05 Hub e tela
- Hub (aiops): gravar `NINF_ZABBIX_URL=https://zabbix-web.ness.com.br/api_jsonrpc.php` (o cliente posta direto nessa URL e a sonda de readiness recusa caminho diferente), `NINF_ZABBIX_ACCESS_CLIENT_ID` e `NINF_ZABBIX_ACCESS_CLIENT_SECRET` no `.env` (release atual e `/opt/n-infraops/app`), **com backup antes** em `/opt/n-infraops/change-backups/<nome>-<data>/`. Recriar `api` e workers com `docker compose -p app ... up -d --no-deps --force-recreate`.
- Decidir o link `tr_events.php` (`incidents.py:394` usa `settings.zabbix_url`).
- Conferir `/zabbix-health`, `/pipeline-health` e `zabbix_readiness`.

### Passo 9: ~01:10 Conferir
`monitor-zabbix-proxy-reconnect.sh` até **18 de 18 frescos** (`stacavprx` fora do critério), fila dos proxies drenando, hosts recentes e a ingestão do Hub (`n_infraops_incidents`). Pelo menos 1 técnico entra pelo M365; a senha antiga é barrada.

### Passo 10: ~01:30 Alertas (só depois da coleta estável)
`ness-zabbix-cutover-enable-alerting` (exige 18 proxies frescos, sem contar o `stacavprx`; chama a API em `127.0.0.1:8080`) liga as ações por lote, observando flood. **Notificações só com a coleta estável e os 18 proxies frescos.** Observar 2 h.

---

**Não rodar** `zabbix-post-cutover-reconcile`: grava o SAML do Authentik por cima do Entra e desfaz o login pelo M365. O script agora recusa sem `ZBX_ALLOW_LEGACY_AUTHENTIK=1`.

## Aborta se (decidir até 02:00)

- Hash ou schema falhar no dump, no envio ou no restore.
- Mais de 20% dos hosts sem dados em 4 h.
- Fila dos proxies crescendo depois de o destino estar no ar.
- Notificação não autorizada saiu.
- 02:00 e o destino ainda não está no ar com os proxies reportando.

## Passo R: Rollback (a origem fica intacta)

1. Hub: `NINF_ZABBIX_URL` de volta à origem; apagar os headers do Access do `.env`; recriar `api` e workers.
2. `cloudflare-zabbix-dns-cutover.sh rollback` (`zabbix.ness.com.br` volta para `144.91.72.202`).
3. **Tela:** desligar o túnel do destino (`systemctl stop cloudflared` na VPS nova) ou apontar a rota `zabbix-web` de volta para a origem. Sem isso, `zabbix-web.ness.com.br` continua mostrando e aceitando escrita no banco restaurado do destino. Depois: parar o `zabbix-server` do destino (`systemctl stop`) e a ponte da origem (`systemctl stop ness-zabbix-cutover-bridge`).
4. Na origem: `sudo systemctl start zabbix-server`.
5. Conferir proxies, Hub e fila. Os proxies enviam o buffer acumulado (24 h cobre a janela).
6. Comunicar e registrar a causa.

---

## Depois do corte (Task 9)

- **D0:** confirmar que a origem não recebe mais proxies; fechar 80/443/2222 na origem só depois de a ponte sair.
- **D0:** testar a conta de emergência (SSH com chave e port forward; `resper` e `akadmin` por senha local).
- **D+1, D+3, D+7:** observar; reportar disponibilidade ao Ricardo.
- **D+7 a D+14:** o Ricardo decide cancelar a `ninfraops-zabbix` (efeito financeiro). Antes, kernel e forense da origem.
- **Depois:** PSK nos 19 proxies, por ondas. Fase B: Access com Entra em GLPI e n8n.
- **Calendário:** o certificado de `zabbix.ness.com.br` vence em **29/11/2026**; o service token `hub-zabbix-api` vence em **09/11/2027**.

## O que o Ricardo precisa fazer

1. Estar disponível sábado das 22:30 às 02:00.
2. Dizer "aborta" se algum critério acima for atingido.
3. Antes de sábado: cobrar o Ismael (buffer nos 16 proxies restantes), gravar a senha do `akadmin`, avisar os técnicos.
