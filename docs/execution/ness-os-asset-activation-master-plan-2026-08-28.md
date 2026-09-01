# Plano mestre de ativação dos ativos ness.OS

- Data: 28/08/2026
- Estado: baseline de planejamento; nenhuma ativação ou corte autorizado por este documento
- Escopo: levar cada ativo do ecossistema a operação comprovada, recuperável e integrada
- Referências canônicas: ADR 0012, ADR 0014, arquitetura oficial e rebaseline de 26/08

## 1. Resultado esperado

O objetivo não é apenas manter serviços no estado `running`. Cada ativo somente
será considerado operacional quando houver evidência de que está:

1. versionado e reproduzível;
2. protegido por identidade, menor privilégio e segredo fora do Git;
3. saudável por teste sintético e observabilidade, não apenas por processo ativo;
4. integrado com dados reais, autorização e isolamento de tenant;
5. coberto por backup, restore e rollback testados;
6. documentado com owner, runbook, SLO, dependências e critério de aceite;
7. testado em cenário positivo, negativo e de degradação.

Esta é a definição operacional de “funcionando perfeitamente” usada neste plano.
Ela não significa ausência absoluta de defeitos; significa operação mensurável,
segura, recuperável e com riscos residuais formalmente aceitos.

## 2. Regra de paralelismo

Os ativos serão preparados em paralelo, mas promovidos conforme seus gates. Não
se deve confundir trabalho simultâneo com ativação simultânea.

| Trilha | Ativos principais | Pode começar agora | Gate de promoção |
|---|---|---:|---|
| T0 — controle e segurança | Git, CI/CD, segredos, cofre, IaC, inventário | sim | G0 — baseline segura |
| T1 — recuperação | Object Storage, Restic, backups, restore e DR | sim | G1 — recuperação comprovada |
| T2 — Zabbix | origem, staging `zbx-prd-01`, proxies, agentes e piloto Cavan | sim | Z-M1 a Z-M5 |
| T3 — identidade e governança | Authentik, RBAC, GLPI, MariaDB e GLPI Agent | sim | G2 — identidade e tenant |
| T4 — Hub ness.OS | Caddy, PostgreSQL, Redis, API, Celery e frontend | sim | G3 — núcleo saudável |
| T5 — integrações | Zabbix, GLPI, RMM, Node-RED, Evolution, Gemini, MISP, Contabo | preparação sim | G4 — fluxo ponta a ponta |
| T6 — SecOps e escala | Wazuh, Google Workspace e expansão de endpoints | desenho/piloto sim | G5 — piloto isolado |

O caminho crítico inicial é: `G0 → G1 → Z-M1…Z-M4 → Z-M5 → G4`.
Wazuh e expansão não bloqueiam o primeiro go-live NOC/ITSM.

## 3. Estado factual consolidado

### 3.1 Zabbix em migração

- Origem canônica: `144.91.72.202`, ativa e preservada como rollback.
- Destino permanente: `zbx-prd-01`, `169.58.234.9`, banco/frontend em UAT,
  `zabbix-server` mascarado e sem coleta produtiva.
- KVM8 Hostinger: fábrica histórica que comprovou restore; retirada do caminho
  crítico e descartável após preservação das evidências.
- Rota oficial: origem intacta → Contabo Object Storage → staging no
  `zbx-prd-01` → validação isolada → UAT → corte DNS.
- Snapshot selecionado: conjunto `20260827T220026-0300`, Restic `96f2a24e`.
- O snapshot atual foi restaurado e importado de forma isolada em 28/08.
  Z-M1, Z-M2 e Z-M3 estão aprovados: rollback validado, 203 tabelas, 677 hosts,
  61.777 itens, 25.229 triggers, integrações inativas e servidor mascarado.
  As evidências estão em `zabbix-prd-01-object-restore-m1-2026-08-28.md` e
  `zabbix-prd-01-object-restore-m2-m3-2026-08-28.md`.
- Um restore anterior, de 22/08, já foi aprovado no destino, mas não substitui a
  homologação do snapshot atual.
- HTTPS, token Zabbix, SAML UAT e RBAC foram revalidados sobre o restore atual em
  29/08; `resper` confirmou o fluxo Authentik até o dashboard, com JIT/SCIM
  desligados e nove Super Admins herdados rebaixados sem exclusão.
- Corte atual: `NO-GO`. Z-M1, Z-M2 e Z-M3 estão aprovados; Z-M4 ainda depende dos
  testes nominais restantes, testes negativos de identidade e piloto Cavan —
  Matriz antes de qualquer decisão Z-M5.

### 3.2 Hub e fontes canônicas

- API, frontend, PostgreSQL, Redis e workers tinham saúde documentada em 27/08.
- Saúde de processo não equivale a integração: Zabbix retornava `Not authorized`;
  GLPI, Atera e Datto não alimentavam o Hub; Authentik estava parcial.
- GLPI está instalado e possui fundação preparada, mas projetos/tarefas ainda não
  foram carregados e a API é interceptada pelo SSO.
- n8n e Evolution estavam ativos, mas seus fluxos não possuem aceite ponta a
  ponta; Node-RED é destino planejado, não ativo atual.
- MISP existe em código/testes mockados, sem integração de produção comprovada.
- Contabo está contido em leitura e `platform_admin`, sem mutações no MVP.

### 3.3 Recuperação, identidade e controle

- Backups externos Restic de AIOps e Zabbix já foram comprovados anteriormente.
- É necessário reconciliar a falha recente por timeout com o último conjunto
  `COMPLETED` e manter RPO de 24 h continuamente.
- Psono Community ainda é PoC; `cofre.ness.com.br` foi aprovado e os bloqueios
  restantes são VPS dedicada, DNS publicado e SMTP.
- Segredos humanos permanecem temporariamente em arquivos root-only; automação
  ainda não foi integralmente migrada para SOPS/age.
- O repositório possui grande volume de alterações não consolidadas e segredos
  históricos; não serve como pacote de release enquanto essa baseline não fechar.

## 4. Gates mestres

### G0 — baseline segura

- credenciais expostas revogadas/rotacionadas por consumidor;
- nenhum segredo válido no Git, artefato ou log;
- worktree classificado e commits revisáveis;
- fontes históricas marcadas como históricas;
- owners técnicos nomeados e mudanças registradas no GLPI;
- CI obrigatório com lint, testes, secret scan e validações IaC.

### G1 — recuperação comprovada

- último backup `COMPLETED` dentro do RPO;
- SHA-256, `restic check` e restore isolado aprovados;
- RTO medido e dentro da meta de 4 h ou exceção formal;
- retenção e proteção do último snapshot válido definidas;
- timers monitorados e falha de backup gera alerta.

### G2 — identidade e tenant

- Authentik homologado por aplicação;
- MFA e menor privilégio para contas privilegiadas;
- login, logout, expiração, revogação e conta desativada testados;
- `platform_admin` aplicado pelo backend, não apenas pela interface;
- teste negativo cross-tenant aprovado;
- duas contas break-glass recuperáveis e auditadas.

### G3 — núcleo saudável

- Caddy, bancos, Redis, API, workers e frontend com healthchecks reais;
- build/release reproduzível por digest;
- métricas RED, filas, banco, TLS e erros frontend monitorados;
- backup/restore e rollback do conjunto comprovados;
- nenhuma tela apresenta placeholder ou dado sintético como real.

### G4 — fluxo operacional ponta a ponta

Um evento sintético autorizado deve percorrer:

`fonte → ingestão → deduplicação → incidente → GLPI → portal → encerramento`

com tenant correto, correlação única, retry sem duplicidade, degradação controlada
e trilha de auditoria.

### G5 — piloto SecOps

- 50–100 endpoints Cavan aprovados;
- Wazuh isolado por tenant, backup/restore e RBAC comprovados;
- zero vazamento cross-tenant;
- EPS/APS, filas, retenção e custo medidos;
- Hostinger preservada até estabilidade e rollback comprovados.

## 5. Plano individual por ativo

### A01 — Repositório Git e release

**Estado:** 227 entradas pendentes na análise inicial, branch à frente do remoto,
artefatos `Zone.Identifier` e documentos operacionais ainda não consolidados.

**Plano:**

1. congelar novas features até classificar alterações por domínio;
2. remover/quarentenar artefatos de sistema e corrigir `.gitignore`;
3. separar commits de segurança, Zabbix, Hub, integrações, IaC e documentação;
4. registrar quais documentos são canônicos, substituídos ou históricos;
5. criar tag/release imutável para cada promoção;
6. exigir PR, revisão e vínculo ao ticket GLPI.

**Testes:** checkout limpo; testes e builds reproduzíveis; scan do snapshot e do
histórico; ausência de arquivos secretos/temporários.

**Aceite:** árvore limpa ou alterações intencionalmente registradas; release pode
ser reconstruída somente com Git, backup e cofre. **Rollback:** tag anterior.

### A02 — CI/CD

**Estado:** há workflows de backend, frontend, lint e Gitleaks; deploy de produção
permanece corretamente desabilitado. Há duplicidade parcial de ferramentas Python.

**Plano:**

1. consolidar Python em um gate com Ruff, formatação, MyPy e Pytest;
2. manter frontend com `npm ci`, lint, TypeScript, testes e build;
3. adicionar validação Terraform, Ansible lint, Compose, shellcheck e testes dos
   toolings Restic/Zabbix;
4. executar Gitleaks no PR e varredura periódica do histórico;
5. gerar SBOM e registrar digests de imagens;
6. liberar deploy apenas por ambiente protegido, aprovação e rollback automático.

**Aceite:** PR não promove com gate vermelho; staging e rollback de release
comprovados. **Rollback:** redeploy do digest/tag anterior, sem mudança de banco não
compatível.

### A03 — Cofre Psono e SOPS/age

**Estado:** Psono é PoC; VPS, domínio e SMTP são bloqueios. Arquivos root-only são
contenção temporária, não solução final.

**Plano:** provisionar VPS exclusiva; hardening; TLS/DNS/SMTP; dois custodians com
MFA; backup Restic; recovery/emergency code offline; estruturar coleções; criar
chaves age com ao menos dois responsáveis; migrar um segredo por vez e revogar o
anterior somente após validar todos os consumidores.

**Testes:** perda de um administrador, recuperação independente, restore do cofre,
segredo expirado, revogação e auditoria sem exposição de valor.

**Aceite:** dois responsáveis recuperam cofre e automação; zero segredo válido em
Git/VPS fora do padrão. **Rollback:** Passbolt Community somente se o PoC Psono
reprovar; nunca retornar segredos ao Git.

### A04 — Contabo, VPS e Terraform

**Estado:** IaC representa parte do alvo, mas contém placeholders, inventário
estático e `prevent_destroy=false`; estado remoto/locking não está comprovado.

**Plano:** congelar `apply`; importar/reconciliar recursos reais; configurar state
remoto cifrado com locking e backup; eliminar placeholders; inventário dinâmico;
ativar proteção contra destruição em recursos permanentes; atualizar IPs/usuários;
executar `plan` em PR e `apply` somente em ambiente protegido.

**Testes:** `plan` sem replace/delete inesperado; detecção de drift; reconstrução de
staging; credencial sem permissão de mutação no conector do Hub.

**Aceite:** zero drift não justificado e rebuild reproduzível. **Rollback:** state
versionado + snapshot/host anterior; `destroy` nunca é rollback.

### A05 — Object Storage e Restic

**Estado:** upload/check/restore foram comprovados para Zabbix e AIOps, mas
retenção, segunda cópia e saúde contínua precisam fechar.

**Plano:** credencial exclusiva por produtor; buckets/prefixos segregados;
criptografia antes do upload; manifesto, SHA-256 e `COMPLETED`; retenção diária,
semanal e mensal preservando o último válido; imutabilidade/versionamento quando
disponível; segunda cópia independente; restore mensal e DR trimestral.

**Testes:** credencial de um produtor não lê outro; snapshot parcial é recusado;
restore com `--verify`; corrupção de arquivo é detectada; timer atrasado alerta.

**Aceite:** RPO ≤24 h, RTO medido, último restore aprovado e capacidade projetada.
**Rollback:** preservar ao menos um snapshot anterior e nunca expurgar durante
incidente/migração.

### A06 — Zabbix origem

**Estado:** produção canônica e rollback; houve incidente XMRig contido. Deve
permanecer intacta durante a migração.

**Plano:** congelar mudança; comprovar backup recente; capturar baseline de versão,
contagens, usuários, scripts, tokens, proxies, NVPS, fila e banco; manter scripts
globais desativados; concluir inspeções IOC pendentes; não executar polimento que
altere a referência enquanto o destino é homologado.

**Testes:** frontend/API, coleta, proxies, backup, restore e segurança. **Aceite:**
origem saudável e recuperável até D+7/D+14 do destino. **Rollback:** é a própria
plataforma de retorno, preservada sem dupla coleta.

### A07 — Zabbix destino `zbx-prd-01`

**Estado:** destino permanente em UAT isolada. Restore antigo aprovado; snapshot
atual ainda sem evidência Z-M1 versionada.

**Plano Z-M1 a Z-M5:**

1. **Z-M1 obter:** restaurar `96f2a24e` em staging novo; `restic check`,
   `COMPLETED`, SHA-256 e `gzip -t`; publicar evidência datada.
2. **Z-M2 restaurar:** criar backup reversível do banco atual do destino; importar
   o snapshot; validar schema, tabelas, hosts, itens, triggers e `dbversion`.
3. **Z-M3 isolar:** server mascarado, processos/10051 ausentes, agent/proxies
   inativos e ações/mídias/conectores zerados; gerar baseline única.
4. **Z-M4 homologar:** revalidar TLS/SAML/MFA/break-glass; comparar origem/destino;
   pilotar Cavan–Matriz por 24–72 h sem canais reais; aceite ness. + Ricardo.
5. **Z-M5 cortar:** janela, TTL, freeze, backup final, GO formal, DNS e reconexão
   de proxies em ondas; canais reais continuam bloqueados no primeiro smoke.

**Abortar:** hash/schema falho, perda de dados, serviço crítico degradado, mais de
20% dos hosts ausentes em quatro horas, backlog crescente ou notificação indevida.

**Aceite:** D+1, D+3 e D+7 sem regressão; backup/restore do destino; origem mantida
7–14 dias. **Rollback:** congelar destino, parar coleta, reverter DNS/proxies,
reativar e validar origem; nunca manter duas instâncias coletando.

### A08 — Zabbix proxies, agentes e qualidade de coleta

**Estado:** inventário possui placeholders/root/chave compartilhada e não pode ser
aplicado. Baseline registra concentração de `unsupported` em FortiGate/links,
além de VMware, Windows/WMI, storage e objetos sem tags/templates.

**Plano:** inventariar 17 proxies e seus owners; remover placeholders; TLS
PSK/certificado; allowlist 10051; reconectar um proxy por vez; corrigir por ondas:
rede/FortiGate, switches/VMware/storage, Windows/Linux, inventário/tags, alertas,
retenção/observabilidade e branding ao final.

**Testes:** piloto Cavan, host de laboratório, item→trigger→recovery, proxy perdido,
TLS inválido, ausência de dupla coleta e rollback export/relink.

**Aceite:** 100% do piloto com template/tags/owner; redução mínima de 70% dos
`unsupported` FortiGate; todo restante classificado; fila e busy estáveis.

### A09 — DNS, TLS, Cloudflare e Caddy

**Estado:** seis domínios/TLS e fechamento de portas diretas foram comprovados;
configuração efetiva e Git precisam permanecer reconciliados.

**Plano:** inventário de zonas/TTL/certificados/owners; `caddy validate`; fixar
digest; reconciliar config efetiva; bloquear acesso direto aos backends; Full
(strict) e allowlists atualizadas; monitorar expiração, renovação e upstreams.

**Testes:** host desconhecido, acesso origin direto, header Authentik forjado,
backend indisponível, certificado inválido/expirando e rollback atômico.

**Aceite:** apenas 80/443 públicos, rotas corretas, nenhum backend exposto e
configuração do Git idêntica à ativa. **Rollback:** Caddyfile/digest e registros DNS
anteriores, com TTL previamente reduzido em cortes.

### A10 — Authentik e RBAC

**Estado:** núcleo saudável, integrações parciais. SAML Zabbix UAT foi comprovado;
Hub, GLPI e n8n ainda exigem homologação completa.

**Plano:** um protocolo/provider por aplicação; callbacks/logout/claims/grupos
documentados; `platform_admin` e papéis por tenant; MFA privilegiado; reduzir
Super Admins sem exclusão por inferência; contas locais apenas break-glass.

**Testes por aplicação:** login, grupo/tenant, MFA, logout, expiração, revogação,
usuário desativado, callback adulterado, IdP indisponível e acesso direto.

**Aceite:** Zabbix, Hub, GLPI e orquestrador homologados individualmente; revogação
dentro do SLA. **Rollback:** provider anterior/config exportada e conta local
break-glass testada.

### A11 — PostgreSQL, TimescaleDB e pgvector

**Estado:** serviço saudável documentado e compartilhado por `nessops`, Authentik
e Evolution; schema/migrations e isolamento ainda precisam formalização.

**Plano:** baseline do schema; garantir extensão `vector`; adotar trilha única de
migration; roles por produto; menor privilégio; testar RLS ou isolamento equivalente;
pooling e TLS coerentes; alarmes de locks, WAL, bloat, disco e slow queries.

**Testes:** base vazia e existente, Timescale, embedding/HNSW, tenant A→B negado,
role de outro produto negada, disco cheio e migration interrompida.

**Aceite:** restore isolado, isolamento comprovado e migration reproduzível.
**Rollback:** dump pré-migration e reversão/forward-fix explicitamente ensaiado.

### A12 — Redis

**Estado:** cache/broker/locks compartilhados; `allkeys-lru` pode expulsar dados de
fila/lock sob pressão.

**Plano:** separar funções/DBs ou instâncias conforme durabilidade; definir política
de eviction por uso; persistência e recuperação; TLS/rede interna; métricas de
memória, evictions, conexões e latência.

**Testes:** restart, memória cheia, lock expirado, broker indisponível e recuperação
sem duplicação. **Aceite:** perda do Redis não perde alerta aceito nem rompe
idempotência. **Rollback:** configuração anterior e redrive controlado.

### A13 — Celery e workers

**Estado:** dois workers configurados; healthchecks atuais podem retornar sucesso
mesmo sem `pong`.

**Plano:** healthcheck fail-closed; heartbeat; fila primária/deferred/ML; retry com
backoff, idempotency key e DLQ; versionar contratos de payload; autoscaling somente
por métricas reais.

**Testes:** enqueue/consume, worker morto, poison message, timeout, retry e restart.
**Aceite:** worker morto torna saúde vermelha; nenhum retry duplica incidente/ticket;
idade/profundidade da fila alertadas. **Rollback:** worker/image anterior compatível
com o payload em trânsito.

### A14 — FastAPI ness.OS

**Estado:** base substancial e testada; configuração parcial, rotas duplicadas e
fontes canônicas ainda não integradas.

**Plano:** matriz rota×auth×role×tenant×mutabilidade; remover duplicidades;
migrations versionadas; HMAC/replay para webhooks; timeout/retry/circuit breaker;
erros padronizados; correlation ID; métricas RED e tracing sem PII.

**Testes:** ingestão/dedupe/persistência/fila; 401/403/429/5xx; replay; cross-tenant;
credencial ausente; dependência lenta e rollback de imagem/schema.

**Aceite:** nenhuma rota sensível sem política; pipeline idempotente sob retry;
lint/type/test verdes. **Rollback:** imagem anterior e migration compatível.

### A15 — Frontend/PWA ness.OS

**Estado:** build e HTTP 200 comprovados; pode parecer saudável sem fontes reais;
não há suíte frontend configurada.

**Plano:** Node LTS e `npm ci`; cliente API tipado; estados por fonte (`real`,
`stale`, `degraded`, `unavailable`); testes de componente e E2E; telemetria JS/Web
Vitals; manifest/service worker e modo offline sem dados falsamente atuais.

**Testes:** login/logout, tenant, dashboard, incidentes, token expirado, API fora,
payload vazio, timeout e usuário sem permissão.

**Aceite:** jornadas críticas verdes e nenhum dado sintético apresentado como real.
**Rollback:** bundle/digest anterior e invalidação controlada do service worker.

### A16 — GLPI e MariaDB

**Estado:** serviço acessível e fundação aprovada; projetos/tarefas não carregados;
API de máquina recebe redirect para Authentik.

**Plano:** rota privada API ou política compatível; app/service token mínimos no
cofre; dry-run remoto; import idempotente do manifesto; entidades por tenant;
catálogo, cinco projetos, 13 WPs e runbooks; SSO nominal e break-glass; backup do
banco, `glpi-data`, documentos e plugins.

**Testes:** criar/atualizar/fechar um ticket; replay pós-timeout sem duplicar;
credencial inválida; entidade errada; cross-tenant; agente duplicado/stale; restore
em host vazio.

**Aceite:** fluxo incidente↔ticket único, manifesto 100%, segregação e restore
integral. **Rollback:** inativar objetos criados pelo importador e restaurar
config/provider; nunca escrever diretamente no banco.

### A17 — GLPI Agent e inventário Cavan

**Estado:** piloto planejado, não homologado em escala.

**Plano:** consentimento/owner; 14 hosts Cavan–Matriz; instalar por RMM em lote
pequeno; reconciliar serial/UUID/hostname/site; definir GLPI como fonte canônica de
cliente, ativo, localização, criticidade e owner; mapear IDs para Zabbix/RMM.

**Testes:** instalação, atualização, remoção, ativo duplicado, dispositivo sem serial
e tenant incorreto. **Aceite:** 100% do piloto reconciliado e freshness monitorada.
**Rollback:** remover agente do lote piloto sem excluir o inventário/auditoria.

### A18 — n8n e migração para Node-RED

**Estado:** n8n ativo com workflows; Node-RED planejado. Integração ponta a ponta
não comprovada.

**Plano:** exportar workflows/credenciais sem valores/hashes; catalogar efeitos;
Node-RED por digest, não-root, editor privado; migrar fluxo a fluxo com idempotência,
retry, erro e DLQ; jamais executar dois motores simultaneamente contra efeito
mutável; observar 48 h por fluxo e 7 dias antes de retirar n8n.

**Testes:** entrada válida, replay, timeout, 429/5xx, credencial revogada, payload
inválido e rollback sem duplicação.

**Aceite:** paridade funcional, falha alertada, zero duplicidade e restore em host
vazio. **Rollback:** n8n parado porém restaurável, reativado com cursor/idempotência.

### A19 — Evolution/WhatsApp

**Estado:** serviço observado ativo; sessão e entrega real não homologadas; fallback
`changeme` deve ser eliminado. É canal secundário, não primário.

**Plano:** rotacionar chave; Manager não público; sessão de saída controlada;
payload mínimo; rate limit; canal alternativo; retenção dos volumes e logs sem PII.

**Testes:** envio/recebimento, chave inválida, sessão desconectada, rate limit,
destinatário inválido e reconnect.

**Aceite:** mensagem sintética auditada, Manager inacessível externamente e canal
alternativo aprovado. **Rollback:** digest anterior e restore dos volumes de sessão.

### A20 — Zabbix → AIOps

**Estado:** API alcançável, mas token documentado como `Not authorized`; integração
não operacional.

**Plano:** revogar token exposto; criar token read-only mínimo após estabilizar o
destino; validar CA/TLS; readiness autenticada; ingestão com freshness, lag,
deduplicação e escopo por tenant; escrita/remediação desligada.

**Testes:** problema autorizado, evento/recovery, token expirado/sem escopo, host
fora do tenant, TLS inválido, replay e indisponibilidade.

**Aceite:** evento sintético vira um incidente e um ticket, sem escrita no Zabbix.
**Rollback:** desligar conector/feature flag sem afetar a coleta canônica.

### A21 — Atera e Datto RMM

**Estado:** clientes implementados; Atera montada, Datto sem router; sem credenciais
de produção e sem integração real.

**Plano:** contrato e owner por provedor; credencial read-only por tenant; paginação,
rate limit e freshness; reconciliar devices/sites com GLPI; ações deny-by-default e
somente HITL após gate específico; expor Datto apenas se a jornada exigir.

**Testes:** 401/403/429/5xx, paginação parcial, tenant cruzado, dispositivo duplicado,
API fora, tentativa de ação sem aprovação e dupla execução.

**Aceite:** inventário conciliado sem duplicidade e falha externa não perde alertas.
**Rollback:** desligar conector mantendo GLPI como cadastro mestre.

### A22 — Gemini

**Estado:** integração configurável para RCA; operação real/custo/privacidade devem
ser homologados.

**Plano:** sanitizer antes do envio; prompt/versionamento; limite de dados e tokens;
timeout/circuit breaker; bypass para baixo risco; saída marcada como assistida e
sempre aprovada por humano; métricas de custo, erro e qualidade.

**Testes:** segredo/PII mascarados, 429/5xx/timeout, resposta inválida, prompt
injection e indisponibilidade sem bloquear incidente.

**Aceite:** nenhum dado proibido sai, custo possui limite/alerta e RCA nunca executa
remediação autonomamente. **Rollback:** feature flag e fluxo sem LLM.

### A23 — MISP

**Estado:** código e testes mockados; produção não comprovada; TLS vem permissivo.

**Plano:** decisão formal GO/NO-GO; owner; CA válida e verificação TLS obrigatória;
credencial mínima; cache, timeout, retry e proveniência do IOC; degradação neutra.

**Testes:** IOC encontrado/não encontrado, TLS inválido, 401/429/5xx, lentidão e
payload malformado.

**Aceite:** falha do MISP não interrompe ingestão e nunca converte erro em IOC
positivo. **Rollback:** feature flag sem mudança do incidente original.

### A24 — Contabo API no Hub

**Estado:** router read-only protegido por `platform_admin`; integração real não
comprovada; mutações corretamente fora do MVP.

**Plano:** credencial read-only; listar/reconciliar VPS, storage, firewalls e estado
com GLPI/Zabbix; freshness e divergências; nenhuma chave ou ação na resposta.

**Testes:** usuário não-admin 403; tentativa POST/PATCH/DELETE 404/405; paginação,
429 e credencial inválida.

**Aceite:** somente GET, zero segredo em log/browser e 100% das VPS justificadas.
**Rollback:** desmontar router/feature flag; nenhuma mutação cloud automática.

### A25 — Wazuh/SecOps

**Estado:** arquitetura e escala planejadas; IaC/Ansible atual é scaffold e não
representa produção confiável. Não bloqueia o primeiro go-live.

**Plano:** corrigir IaC/inventário; PoC single-node isolada; 50–100 endpoints Cavan;
RBAC/DLS/API por tenant; MISP/Gemini opcionais; medir EPS/APS, fila, drops, retenção,
CPU/RAM/disco; backup/restore; depois Onda 1 com oito VPS e Onda 2 HA com dez,
somente após Gate Financeiro e núcleo aprovado.

**Testes:** agente offline, burst, indexer/manager perdido, cross-tenant, restore,
regra falsa positiva e rollback/desinstalação do piloto.

**Aceite piloto:** zero cross-tenant, nenhum evento perdido sem alerta, restore
aprovado e custo medido. **Rollback:** remover/reapontar agentes piloto e manter
Hostinger até 7–14 dias de estabilidade.

### A26 — Google Workspace Cavan

**Estado:** planejado; delegação read-only ainda não concedida. Alert Center fica
fora do piloto por exigir escopo com escrita.

**Plano:** aprovação formal; conta de serviço e escopos mínimos de auditoria;
nenhuma coleta de conteúdo/token; tenant Cavan; retenção e owners; ingestão em
staging antes do portal/SecOps.

**Testes:** escopo não autorizado, usuário/tenant incorreto, API indisponível,
paginação e revogação da delegação.

**Aceite:** somente metadados aprovados, zero conteúdo e revogação comprovada.
**Rollback:** revogar delegação e desligar conector.

### A27 — Observabilidade, SLO e DR transversal

**Estado:** há logs e backups, mas falta uma visão única de saúde e SLO por ativo.

**Plano:** catálogo de SLIs/SLOs; monitor externo; dashboards de disponibilidade,
latência, erro, fila, freshness, backup e capacidade; alertas com owner/runbook;
teste sintético por jornada; exercício DR trimestral e revisão D+1/D+3/D+7 após
mudanças críticas.

**Testes:** desligar dependência em staging, expirar credencial, atrasar backup,
saturar fila controladamente e executar restore completo.

**Aceite:** falha é detectada antes do usuário, cada alerta crítico tem owner e
runbook, RPO/RTO são medidos. **Rollback:** retornar ao conjunto de versões e dados
do último exercício aprovado.

## 6. Ordem operacional imediata

### Frente paralela 1 — hoje

1. declarar incidente de credenciais versionadas e rotacionar/revogar;
2. classificar o worktree e congelar novas features;
3. nomear owners das trilhas;
4. reconciliar documentos: plano Zabbix de 28/08 prevalece; KVM8 é histórica;
5. registrar no GLPI os ativos, WPs, gates e evidências.

### Frente paralela 2 — recuperação

1. confirmar último backup Zabbix/AIOps dentro do RPO;
2. fechar timeout, retenção e alerta dos timers;
3. executar restore mensal e registrar RTO;
4. iniciar Psono/SOPS-age sem bloquear a validação técnica do staging.

### Frente paralela 3 — Zabbix

1. executar e documentar Z-M1 do snapshot `96f2a24e`;
2. executar Z-M2/Z-M3 mantendo isolamento fail-closed;
3. reconciliar dados e pilotar Cavan em Z-M4;
4. somente então preparar a decisão Z-M5.

### Frente paralela 4 — identidade/GLPI

1. homologar Authentik por aplicação;
2. tornar a rota de máquina GLPI funcional;
3. executar dry-run remoto e importar fundação de forma idempotente;
4. ativar GLPI Agent somente no piloto.

### Frente paralela 5 — Hub

1. corrigir healthcheck dos workers e política Redis;
2. consolidar CI, migrations e matriz de autorização;
3. criar testes frontend/E2E e observabilidade;
4. manter indicadores como indisponíveis/stale até as fontes reais entrarem.

### Frente paralela 6 — integrações e SecOps

1. preparar contratos, credenciais mínimas e testes negativos;
2. ativar Zabbix→AIOps somente após o Zabbix estabilizar;
3. provar AIOps→GLPI antes de RMM/WhatsApp;
4. migrar n8n→Node-RED fluxo a fluxo;
5. manter Wazuh em planejamento/PoC até G4 e Gate Financeiro.

## 7. Critério de encerramento do programa

O programa termina quando:

- Zabbix opera no destino com origem liberada somente após D+7/D+14;
- cada sistema canônico entrega dados reais e reconciliados ao ness.OS;
- um incidente percorre o fluxo completo sem duplicidade e com isolamento;
- todos os ativos críticos possuem owner, SLO, runbook e alerta;
- backup, restore, rollback e DR foram demonstrados;
- identidade, MFA, revogação e break-glass foram testados por aplicação;
- nenhum segredo válido está no Git e dois responsáveis recuperam o cofre;
- CI/CD produz release imutável e reversível;
- riscos residuais possuem severidade, owner, prazo e aceite formal.

## 8. Documentos que precisam de reconciliação

1. O plano Zabbix de 28/08 substitui a rota via KVM8 dos documentos anteriores.
2. Usar prefixo `Z-M1`…`Z-M5` para não confundir com os marcos M1…M5 do plano
   diretor do ecossistema.
3. Atualizar o quadro mestre do `ecosystem-completion-plan.md`, que ainda manda
   terminar a transmutação KVM8 e contratar destino já existente.
4. Marcar `infra/docs/migration-checklist.md` e o runbook Azure como históricos.
5. Atualizar o protocolo de identidade Zabbix para “SSO Authentik + MFA”, pois a
   implementação homologada é SAML, não OIDC.
6. Reconciliar inventários Ansible/Terraform com usuários, IPs, portas e recursos
   reais antes de qualquer `apply`.

## 9. Referências principais

- `docs/architecture/ness-os-official-architecture.md`
- `docs/adr/0012-ness-os-official-architecture.md`
- `docs/adr/0014-staged-ness-os-delivery.md`
- `docs/execution/ness-os-rebaseline-2026-08-26.md`
- `docs/execution/zabbix-data-quality-and-visibility-plan-2026-08-28.md`
- `docs/execution/zabbix-post-restore-transmutation-cutover-checklist.md`
- `docs/execution/gate-0-status.md`
- `docs/ecosystem-completion-plan.md`
- `infra/docs/as-built-vps.md`
- `config/glpi/ness-os-foundation-v1.yaml`
