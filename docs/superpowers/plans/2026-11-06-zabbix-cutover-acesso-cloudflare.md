# Zabbix: cutover para a VPS nova com acesso por Cloudflare Access — plano

> **Para quem executa:** use superpowers:executing-plans (inline) ou subagent-driven-development. Passos com `- [ ]`. Passo marcado **[FRASE]** só roda com a frase explícita do Ricardo, dizendo o efeito.

**Objetivo:** tirar a tela web do Zabbix da internet (túnel + Cloudflare Access, login por pessoa, home office sem VPN) e trocar a produção atual (`144.91.72.202`) pela VPS nova (`169.58.234.9`), sem perder coleta.

**Arquitetura:** a tela e a API ficam atrás de `cloudflared` (saída apenas, 80/443 fechadas); a porta 10051 fica só para os 19 proxies (lista de IPs); o Hub entra na API com service token do Access. O cutover reaproveita o checklist e os scripts que já existem.

**Spec/decisões:** [ADR 0015](../../adr/0015-entra-id-identity-local-authorization.md) (pontos 3 a 5), [desenho de perímetro](../specs/2026-11-05-identity-access-perimeter-design.md), [checklist de cutover](../../execution/zabbix-post-restore-transmutation-cutover-checklist.md), [spec da VPS permanente](../../procurement/zabbix-contabo-permanent-spec-2026-08-24.md).

## Medido em leitura (06/11/2026)

| Fato | Valor | Efeito no plano |
|---|---|---|
| Produção atual | 80, 443, 10051 e SSH abertos para qualquer origem; PHP 8.2.35 (corrigido em 22/10) | Exposta até o corte; sem urgência de PHP |
| VPS nova | Server e Apache desligados; MariaDB 28 GB; PHP 8.3.6 com o patch das CVE-2026-109618/9; Fail2ban ativo; 443 só Cloudflare; 10051 só 19 IPs; sem `cloudflared` | Casca pronta, sem coleta |
| Banco da VPS nova | último acesso de proxy em **11/10/2026 22:00** | ~25 dias defasado: só o dump final serve |
| Proxies | 19, todos ativos, **todos `tls_connect=1` (sem criptografia)** | PSK é trabalho próprio, depois do corte |
| Nome dos proxies | `zabbix.ness.com.br` (default da role); `monitoramento.ness.com.br` não tem DNS | A web não pode ir para o túnel com esse mesmo nome |
| Hub | `NINF_ZABBIX_URL=https://zabbix.ness.com.br/api_jsonrpc.php`, token Bearer, ~250 mil chamadas nos logs atuais | Hub precisa de service token do Access |
| DNS | `zabbix.ness.com.br` A `144.91.72.202`, TTL ~246 s, **sem proxy** (`proxied:false`) | Script `cloudflare-zabbix-dns-cutover.sh` já faz cutover e rollback |
| Script de monitoramento | `monitor-zabbix-proxy-reconnect.sh` espera `18/18` | O banco tem **19** proxies: reconciliar antes |

Não verificado: `ProxyOfflineBuffer`/`ConfigFrequency` dos proxies, duração real do dump e restore de ~76 GB, estado de actions/media types na VPS nova.

## Restrições globais

- ADR 0015: o provedor autentica e o Zabbix autoriza (sem JIT); cliente nunca alcança o Zabbix; conta local de emergência e SSH com chave e origem restrita ficam; **Entra e SAML só na Fase B**.
- Custo: Cloudflare Free (≤ 50 usuários; hoje ≤ 5 técnicos). Sem licença nova.
- Contraria o ADR 0015 ("não mexer em Cloudflare/DNS antes do aceite do MVP"): Tasks 4 e 6 em diante pedem **[FRASE]** do Ricardo.
- Segredos só em `projetos.env` (gravados pelo Ricardo) ou Psono; nada em log nem em arquivo versionado. Actions, media types e connectors desligados no restore; `EnableGlobalScripts=0`.
- Origem (`144.91.72.202`) preservada 7–14 dias para rollback; nunca duas instâncias coletando.

## Review Focus

- Proxy sem buffer suficiente perde dados na janela: medir o buffer antes de marcar a hora.
- DNS único para proxies e web: separar nomes antes de proxiar qualquer coisa.
- Hub sem credencial do Access recebe 302/403 e para de ingerir: testar a API pelo túnel antes do corte.
- Restore liga actions e notificações junto: flood de e-mail e tickets no GLPI.
- Dupla coleta se origem e destino rodarem juntos.
- Access fora do ar ou OTP sem entrega: quebra de vidro testada antes de fechar 443.

---

### Task 1: Decisões e pré-requisitos (sem mudança)

**Files:** este plano; `docs/execution/zabbix-cutover-2026-11.md` (evidência, criar na execução).

- [ ] **Step 1:** Ricardo informa: hostname da tela aprovado em 06/11: `zabbix-web.ness.com.br` (`zabbix.ness.com.br` fica só para proxies). IdP: Entra (confirmado 06/11). Sem grupo na Cloudflare e sem lista de e-mails: o Access só libera quem entra (`@ness.com.br`, MFA dos security defaults do Entra); papel e permissão ficam em usuários e grupos do próprio Zabbix, cadastrados antes, sem JIT (ADR 0015). Informar quem opera a janela.
- [ ] **Step 2:** Ricardo grava como `dev` em `/srv/dev/secrets/projetos.env` um token Cloudflare com escopo mínimo (DNS da zona + Access + Tunnel). O agente só lê o arquivo.
- [ ] **Step 3:** Ler `ProxyOfflineBuffer` e `ConfigFrequency` de 2 proxies (somente leitura, SSH autorizado) e reconciliar 18 × 19 no `monitor-zabbix-proxy-reconnect.sh`. **Resolvido em 06/11:** o 19º é o `stacavprx` (Cavan, Santa Lucia), máquina já migrada e sem acesso desde 11/09; fica fora do critério de sucesso e o monitor **precisa de ajuste antes da janela**: `infra/scripts/monitor-zabbix-proxy-reconnect.sh` conta todas as linhas de `proxy` e só aceita `18/18`; com o `stacavprx` no banco restaurado o resultado é `18/19` e dá timeout. Correção (PR próprio, pré-requisito da Task 7): excluir o `stacavprx` na consulta (`WHERE p.name<>'stacavprx'`) e manter a meta 18/18. Seus 4 hosts e 5 problemas antigos seguem ativos no Zabbix; limpeza (desativar, não apagar) é decisão à parte.
- **Verifica:** buffer ≥ duração estimada da janela; contagem de proxies explicada.

### Task 2: Restore atual na VPS nova, isolado e medido **[FEITA em 09/11]**

**Medido em 09/11** (dump noturno de 08/11, 5,65 GB, SHA-256 conferido contra o `SHA256SUMS` da origem):
- Envio da origem para a VPS nova por pipe SSH, sem restic: ~15 min (~6 MB/s).
- Restore (`ness-zabbix-native-restore restore`): **3.497 s (58 min)**, banco final 30 GB.
- Resultado: `restore=PASS`, 203 tabelas, 708 hosts, 67.183 itens, 28.100 triggers, `dbversion=7000000`, actions/media/connectors ativos = 0, `zabbix-server` inativo e mascarado.
- **Repositório restic `zabbix-prod`:** a senha do `backup-s3.env` da VPS nova não o abre (só abre `zbx-prd-01`). Por isso o dump do cutover NÃO passa pelo restic: segue por pipe SSH, com SHA-256 conferido nos dois lados.
- **Janela real da Task 7:** dump ~32 min + envio ~15 min + restore ~58 min + religar/DNS/conferência ~15 min = **~2 h** com a coleta parada. Exige `ProxyOfflineBuffer` ≥ 24 h nos proxies antes (script `infra/scripts/zabbix-proxy-set-offline-buffer.sh`, rodado pelo Ismael).

### Task 3: Web da VPS nova só em loopback **[FEITA em 09/11]**

- Apache só em `127.0.0.1:8080` (vhost `ness-zabbix-tunnel`, `Require ip 127.0.0.1`, sem 80/443); vhosts de produção/UAT desabilitados; backup do `ports.conf` em `/root/apache-task3-*`. `zabbix-server` segue mascarado.
- Verificado na VPS: `/` 200, `/conf`, `/include`, `/app` 403, API `apiinfo.version` responde; `ss -ltn` sem 80/443. `Admin` e `guest` no grupo `Disabled`; `EnableGlobalScripts=0`.
- `ness-zabbix-cutover-enable-production` roda com `ZBX_WEB_EXPOSURE=closed` (default).

### Task 4: Túnel e Access na VPS nova **[FRASE]**

- [ ] **Step 1:** Instalar `cloudflared`, criar o túnel e a rota `zabbix-web.ness.com.br` → `http://127.0.0.1:8080` (a porta do vhost `ness-zabbix-tunnel`, Task 3). Saída apenas.
- [ ] **Step 2:** Aplicação no Access com política *allow* `@ness.com.br` via Entra, deny-by-default, sessão curta (desenho de perímetro, ADR 0015 ponto 4). Quem passa pelo Access ainda precisa de usuário cadastrado no Zabbix; cadastrar 2 ou 3 técnicos só para o teste.
- [ ] **Step 3:** Service token do Hub com política *Service Auth* só para `/api_jsonrpc.php`.
- [ ] **Step 4:** Teste com 2 ou 3 técnicos em casa e em 4G: entram, e um e-mail fora da lista é barrado.
- **Verifica:** login por pessoa, registro por pessoa nos logs do Access, API responde 200 ao Hub e 403 sem o token.
- **Rollback:** desligar o túnel e apagar a aplicação do Access; nada de produção usa o nome novo.

### Task 5: Hub chama a API pelo Access (código)

**Files:** `app/backend/app/integrations/zabbix.py`, `app/backend/app/api/routers/secops.py` (`_zabbix()`, linhas ~200–218, chamador separado), `app/backend/app/config.py`, `app/.env.example`, `app/backend/tests/`.

- [ ] **Step 1: Teste que falha** `test_zabbix_client_sends_access_headers`: com `NINF_ZABBIX_ACCESS_CLIENT_ID/SECRET` definidos, o cliente envia `CF-Access-Client-Id` e `CF-Access-Client-Secret`; sem eles, nenhum header extra; nenhum valor aparece em log.
- [ ] **Step 2: Implementar** os dois campos opcionais em `Settings` e os headers em `zabbix.py` (linhas ~49–56 e ~80). Migrar `_zabbix()` do `secops.py` para o `ZabbixClient` (um só ponto de chamada) e cobrir com teste: `test_secops_zabbix_call_sends_access_headers`. Sem abstração nova.
- [ ] **Step 3:** CI verde, revisor Sonnet e Codex tratados; **promoção só com [FRASE]**. Os valores vão no `.env` da produção pelo procedimento já usado (backup do `.env`, recriar `api` e workers).
- **Verifica:** `pytest` passa; em produção, `zabbix_readiness` continua `ok` com a URL nova.
- **Rollback:** voltar `NINF_ZABBIX_URL` ao nome antigo e recriar os serviços.

### Task 6: Separar os nomes de DNS **[FRASE]**

- [ ] **Step 1:** Criar `zabbix-web.ness.com.br` (Task 4) e reduzir o TTL de `zabbix.ness.com.br` ao mínimo, 24 h antes da janela.
- [ ] **Step 2:** Até a Task 7 terminar, `zabbix-web` aponta para a **origem** (`144.91.72.202`) ou o Hub continua nela: o destino ainda é um restore isolado e descartável, e escritas do Hub (ex.: `acknowledge_resolution_once()`) lá seriam perdidas pelo dump final. A tela e o Hub só passam a `zabbix-web` no destino dentro da Task 7 (Step 5), depois do restore final.
- **Verifica:** `zabbix.ness.com.br` só recebe proxies; `check` do `cloudflare-zabbix-dns-cutover.sh` passa.

### Task 7: Janela de cutover **[FRASE]** (hora marcada)

- [ ] **Step 1:** Congelar mudanças; avisar; registrar hora-limite do rollback. Medir a fila dos proxies antes.
- [ ] **Step 2:** **Parar a coleta antes do dump** (`systemctl stop zabbix-server`; `mariadb` e `apache2` continuam, nada escreve em `history`). O dump noturno **não serve** para isso: `zabbix-nightly-backup.sh` exige `zabbix-server` ativo (linha 34) e usa `--single-transaction`, então o que os proxies enviassem durante os ~32 min ficaria fora e não seria reenviado. Pré-requisito (PR próprio com revisor, antes da janela): variante `zabbix-cutover-backup.sh` que exige o server **parado**, tira o dump com `mariadb-dump` e gera `SHA256SUMS`/manifesto como o noturno. Depois: `gzip -t` + SHA-256; **enviar por pipe SSH direto da origem para a VPS nova** (como na Task 2: `ssh origem 'sudo cat <dump>' | ssh destino 'sudo tee /var/lib/ness-os/restore-input/<dir>/dbzabbix.sql.gz'`, ~15 min), **sem restic**: a senha do `backup-s3.env` da VPS nova não abre o repositório `zabbix-prod`. Conferir o SHA-256 do arquivo recebido contra o `SHA256SUMS` do cutover e o `-- Dump completed`; o restore usa `ness-zabbix-native-restore restore <dump> <sha256>` (não o stage-restore). O dataset `zabbix-cutover` do restic (#219) fica disponível como cópia de segurança fora da máquina, a enviar depois, se a senha for corrigida. A coleta fica parada do dump até a Step 6; os proxies seguram o buffer nesse intervalo (meça com a resposta do dev).
- [ ] **Step 3:** Restaurar na VPS nova; repetir as contagens da Task 2; confirmar actions/media/connectors = 0.
- [ ] **Step 4:** Ligar o `zabbix-server` na VPS nova com **notificações ainda desligadas**, sem abrir 80/443 (ver aviso da Task 3).
- [ ] **Step 5:** `cloudflare-zabbix-dns-cutover.sh cutover`; apontar o Hub (`NINF_ZABBIX_URL`) e `zabbix-web` para o destino; ajustar o allowlist da 10051 (já com os 19 IPs) e remover a regra da ponte.
- [ ] **Step 6:** Acompanhar `monitor-zabbix-proxy-reconnect.sh` até todos os proxies; checar fila, hosts recentes e a ingestão do Hub (`n_infraops_incidents`).
- [ ] **Step 7:** Após coleta estável, ligar actions por lote, observando flood. Observar 2 h.
- **Janela estimada (com a coleta parada desde o início do dump):** dump ~32 min + envio ~15 min + restore ~58 min (medido na Task 2) + religar ~15 min (~2 h); a meta é caber no buffer dos proxies. Se não couber, subir `ProxyOfflineBuffer` antes (role `zabbix-proxy`), nunca estender a janela.
- **Aborta se:** hash/schema falhar, > 20% dos hosts sem dados em 4 h, fila crescendo, ou notificação não autorizada.
- **Verifica:** `ready` do Hub, proxies reportando sem duplicar, tela acessível só pelo Access.

### Task 8: Rollback

- [ ] Voltar `NINF_ZABBIX_URL` do Hub à origem (rollback da Task 5) e recriar `api` e workers; apontar `zabbix-web` de volta à origem (ou desligar o túnel do destino); parar `zabbix-server` do destino; `cloudflare-zabbix-dns-cutover.sh rollback`; iniciar a origem; confirmar proxies, Hub e fila; comunicar e registrar a causa. A origem segue intacta.

### Task 9: Depois do corte

- [ ] **Step 1:** Fechar 80/443/2222 só na VPS nova (já nasce assim) e confirmar que a origem não recebe mais proxies. Testar a conta de emergência (SSH com chave + port forward).
- [ ] **Step 2:** PSK nos 19 proxies, em ondas, com `zabbix_proxy_tls_connect: psk` e `reconnect-proxies.yml --limit`; só depois fechar `noencryption`. Exige o inventário sem `PLACEHOLDER_IP` (17 hoje).
- [ ] **Step 3:** Kernel da origem e forense antes de reaproveitar a máquina; observação D+1, D+3, D+7.
- [ ] **Step 4 (Fase B):** trocar o IdP do Access para o Entra e ligar SAML no Zabbix, sem JIT.

## Autocheck

- Cobertura: acesso (Tasks 3–6), cutover (7), rollback (8), endurecimento (9). PSK ficou fora da janela de propósito.
- Lacunas assumidas: buffer dos proxies (resposta do dev) e duração do restore (Task 2) ainda não medidos. `stacavprx` (máquina migrada) fora do critério.
