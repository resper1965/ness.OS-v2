# ness.OS Complete Implementation Route

> **Sequência consolidada no [plano master](2026-10-12-ness-os-plano-master.md).**
> Este roteiro conserva detalhe por domínio. Decisões, prioridade e restrição
> de execução do master prevalecem sobre instruções históricas divergentes.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this route one checkbox at a time. No production change advances a gate merely because a service is online.

**Goal:** concluir o ness.OS como uma operação segura e verificável: monitoramento confiável, ITSM, Hub de incidentes, identidade, cofre, AIOps assistido, SecOps e visões por tenant.

**Architecture:** Zabbix é a fonte de telemetria; GLPI é a fonte de ativos e tickets; Authentik é a identidade; Psono guarda segredos; o Hub correlaciona incidentes e apresenta a operação. Cada fonte mantém seu sistema de registro e só fornece dados ao Hub depois de comprovar escopo, frescor, RBAC, backup e rollback. Wazuh, Google Workspace, automações e portal executivo são extensões pós-MVP e jamais falsificam estado quando ainda não estão entregues.

**Tech Stack:** Zabbix 7.0, GLPI, Authentik, Psono Community, FastAPI, PostgreSQL, Redis, Celery, React/Vite PWA, Docker Compose, Restic/S3 Contabo, Cloudflare, Node-RED e Wazuh.

**Spec:** `docs/PROJECT_CONTEXT.md`, `docs/execution/implementation-plan-2026-10-11.md`, `docs/execution/ness-os-asset-activation-master-plan-2026-08-28.md` e `docs/execution/goal-completion-audit-2026-09-08.md`.

## Global Constraints

- A última evidência operacional consolidada é de 2026-09-28. Nenhuma condição de produção deve ser presumida válida em 2026-10-11 sem nova coleta datada.
- Nenhum segredo, chave privada, token, dump ou cookie entra no Git, documentação, logs ou evidência.
- Produção só muda com: owner, janela, backup válido, rollback testado, dry-run quando aplicável e evidência posterior.
- Zabbix de origem `144.91.72.202` permanece rollback até D+7/D+14 do destino `zbx-prd-01`; nunca manter dupla coleta.
- Usar API/interface oficial para Zabbix e GLPI; nunca SQL direto para alterar objetos operacionais.
- Dados de tenant exigem proveniência, escopo e horário de coleta. Ausência/falha deve aparecer como `unavailable` ou `stale`, nunca como zero ou saudável.
- MFA é obrigatório para contas privilegiadas; contas locais são apenas break-glass auditado.
- Branding ness. somente depois da estabilidade funcional: `ness.` em caixa baixa, Montserrat 500, BlueDot `#00ade8`, adaptação preto/branco ao fundo e camada reversível.
- Contabo API é somente leitura até existir uma mudança específica aprovada. Wazuh não inicia em produção antes do MVP aceito, BOM e orçamento aprovados.

## Review Focus

- Release diferente do repositório: impedir promoção quando commit, imagens, Compose e rollback não forem a mesma unidade verificável.
- Falha de backup ou restore: rejeitar snapshot parcial/antigo e avisar antes de violar RPO de 24 horas.
- Sinal sem tenant verificável: rejeitar/quarentenar; nunca inferir tenant pelo frontend ou abrir ticket em cliente errado.
- Retry, reentrega ou queda de GLPI/Redis: preservar no máximo um incidente e um ticket por evento de origem.
- Zabbix durante corte: impedir listeners, proxies, ações e mídias no destino até a decisão formal de GO; abortar se houver dupla coleta ou regressão.

## Painel de pendências completo

| ID | Frente | Pendência objetiva | Gate de encerramento |
| --- | --- | --- | --- |
| R01–R05 | Release e Git | baseline reproduzível, CI limpo, digests, SBOM e rollback | G0 `PASS` |
| B01–B06 | Backup e DR | revalidação dentro do RPO, retenção, alerta de timer, RTO e segunda cópia | G1 `PASS` |
| I01–I07 | Authentik e RBAC | MFA, revogação, expiração, break-glass e teste por aplicação/tenant | G2 `PASS` |
| S01–S06 | Psono e segredos | dois custodians, MFA, recovery offline, SMTP, SOPS/age e rotação por consumidor | Cofre operacional |
| Z01–Z18 | Zabbix | M1–M5, piloto Cavan, templates, tags, qualidade, alertas, mapas e painéis | Z-M5 + D+7 |
| G01–G09 | GLPI | API de máquina, entidades, catálogo, SLA, inventário, agente e tickets | GLPI integrado |
| H01–H12 | Hub | runtime, migrations, Redis/Celery, RBAC, fonte/frescor, UI e release | G3 `PASS` |
| X01–X06 | Integração MVP | Zabbix → Hub → GLPI, replay, degradação, auditoria e observação | G4 + D+7 |
| A01–A08 | AIOps | contrato de incidentes, triagem, RCA assistida, Node-RED, RMM e métricas | Automação assistida |
| W01–W09 | SecOps | BOM Wazuh, hub-spoke, piloto, Google Workspace, isolamento e escala | G5 `PASS` |
| E01–E08 | Experiência | PWA, dashboards, runbooks, SLOs, branding e visão executiva/cliente | Operação sustentada |

## Ordem obrigatória

```text
0. Revalidar fatos -> 1. G0 Release -> 2. G1 Backup/DR -> 3. G2 Identidade/Cofre
-> 4. Zabbix definitivo -> 5. GLPI operacional -> 6. Hub confiável
-> 7. Aceite Zabbix–Hub–GLPI -> 8. AIOps assistido
-> 9. Wazuh/Workspace -> 10. Portal, PWA, branding e escala contínua
```

As etapas 1–3 podem produzir artefatos em paralelo, mas nenhuma escrita produtiva das etapas 4–10 ocorre antes de G0. Branding e dashboards finais acompanham cada promoção, porém não antecipam qualidade de dados.

---

## Phase 0 — congelar fatos e iniciar a trilha de evidência

**Owner de execução:** ness. operações. **Aprovação:** Ricardo Esper. **Saída:** fotografia atual e log de mudança para cada frente.

### Task 0.1: Criar o registro de retomada

**Files:**
- Create: `docs/execution/project-stage-2026-10-11.md`
- Modify: `docs/execution/ness-os-operationalization-log.md`

- [ ] Registrar data/hora BRT e UTC, branch, `git rev-parse HEAD`, ambiente, owner e objetivo da retomada.
- [ ] Executar somente leitura nos serviços Zabbix origem/destino, AIOps, GLPI, Authentik, Psono, Hub e Object Storage; registrar acesso negado como bloqueio, sem improvisar credencial.
- [ ] Para cada serviço, registrar versão, URL, estado, listener exposto, backup mais recente, último teste conhecido e risco.
- [ ] Marcar explicitamente cada número antigo como histórico quando não tiver coleta nova.
- [ ] Commit: `docs(stage): record 2026-10-11 operational baseline`.

**Exit evidence:** um único estágio datado, sem segredos, separando `observado agora`, `histórico` e `desconhecido`.

### Task 0.2: Criar o livro de gates

**Files:**
- Create: `docs/execution/gates/ness-os-gate-register.md`

- [ ] Criar uma linha para G0, G1, G2, Z-M1 a Z-M5, G3, G4 e G5 com owner, pré-condição, rollback, data de evidência e estado inicial `OPEN`.
- [ ] Vincular cada gate ao ticket GLPI de mudança antes de qualquer alteração produtiva.
- [ ] Definir que somente Ricardo pode marcar `GO` para corte Zabbix, integração produtiva e expansão de endpoint.
- [ ] Commit: `docs(gate): add ness os gate register`.

---

## Phase 1 — G0: release reproduzível e seguro

**Não avançar para deploy/corte se qualquer item falhar.**

### Task 1.1: Reconciliar repositório e runtime

**Files:**
- Modify: `docs/execution/gates/phase-0-recovery-release.md`
- Create: `docs/execution/evidence/release-runtime-reconciliation-YYYY-MM-DD.md`

- [ ] Confirmar árvore limpa com `git status --short`; se houver mudança, classificá-la por domínio ou mover para quarentena versionada fora do checkout.
- [ ] Identificar o commit de cada runtime: Hub/AIOps, frontend, Compose, Zabbix tooling e infraestrutura.
- [ ] Comparar hashes do runtime com a release candidata; diferença sem commit correspondente mantém G0 em `FAIL`.
- [ ] Listar todas as imagens em execução e registrar digest imutável; substituir tags mutáveis antes da promoção.
- [ ] Registrar o resultado e o commit candidato, sem reescrever evidência histórica.

### Task 1.2: Fechar CI e cadeia de artefatos

**Files:**
- Modify: workflows existentes em `.github/workflows/`
- Create: `docs/execution/evidence/release-ci-YYYY-MM-DD.md`

- [ ] Rodar em runner limpo: backend, frontend, lint, tipos, testes de scripts, secret scan, Compose validation e SBOM.
- [ ] Falhar a pipeline se imagem estiver sem digest, se secret scan encontrar credencial válida, ou se o Compose referenciar arquivo não versionado.
- [ ] Publicar SBOM da release e associar hashes de imagens à tag/commit.
- [ ] Repetir a pipeline a partir de checkout limpo; ambos os resultados devem coincidir.

### Task 1.3: Ensaiar rollback de release

**Files:**
- Create: `docs/runbooks/release-rollback.md`
- Create: `docs/execution/evidence/release-rollback-YYYY-MM-DD.md`

- [ ] Selecionar uma release anterior compatível e registrar seus digests, config e migration.
- [ ] Em ambiente isolado, promover a candidata e reverter para a anterior; verificar API, worker, banco e UI depois de cada transição.
- [ ] Proibir rollback que exija apagar banco; usar migration compatível ou forward-fix documentado.
- [ ] Registrar RTO medido e lacunas.

### Task 1.4: Aprovar G0

- [ ] Conferir os três conjuntos de evidências acima e `git diff --check`.
- [ ] Atualizar `phase-0-recovery-release.md` para `PASS` somente se commit, CI, digest, SBOM e rollback forem datados e aprovados.
- [ ] Caso contrário, manter `FAIL`, abrir item corretivo específico e não iniciar mudança produtiva dependente.

**Exit evidence:** G0 `PASS`, release reconstruível e reversível.

---

## Phase 2 — G1: backup, restore e DR contínuos

### Task 2.1: Revalidar cada conjunto canônico

**Files:**
- Modify: `docs/execution/backup-verification-2026-08-21.md`
- Create: `docs/execution/evidence/backup-dr-YYYY-MM-DD.md`

- [ ] Para Zabbix, AIOps/Hub, GLPI/MariaDB, Psono e Authentik/PostgreSQL: localizar o último conjunto `COMPLETED` dentro de 24 h.
- [ ] Validar manifesto, SHA-256, `restic check` e recusar conjunto incompleto.
- [ ] Restaurar um conjunto por sistema em ambiente isolado, sem iniciar conectores, agentes, notificações ou escrita em produção.
- [ ] Medir início/fim e registrar RTO real contra a meta de 4 h; registrar exceção formal quando exceder.
- [ ] Não remover último snapshot válido nem banco restaurado que ainda seja rollback.

### Task 2.2: Fechar retenção e monitoramento

**Files:**
- Modify: `infra/scripts/ness-object-storage-restic.sh`
- Modify: units/timers `ness-*-object-storage-backup`
- Create: `docs/runbooks/backup-retention-and-restore.md`

- [ ] Criar credencial S3 exclusiva por produtor e prefixos isolados; testar que um produtor não lista o outro.
- [ ] Fixar retenção diária, semanal e mensal, preservando o último snapshot válido; ativar versionamento/imutabilidade quando disponível.
- [ ] Implementar alerta para timer falho, ausência de `COMPLETED`, RPO >24h e `restic check` falho.
- [ ] Definir segunda cópia independente e registrar custo/capacidade antes de ativá-la.
- [ ] Agendar restore mensal e DR trimestral; cada execução atualiza evidência.

**Exit evidence:** G1 `PASS`, RPO <=24 h, RTO medido, último restore aprovado e alertas de backup observáveis.

---

## Phase 3 — G2: identidade, RBAC e cofre

### Task 3.1: Homologar Authentik por aplicação

**Files:**
- Modify: `docs/security/access-control-matrix.md`
- Create: `docs/execution/evidence/authentik-application-uat-YYYY-MM-DD.md`

- [ ] Inventariar Hub, Zabbix, GLPI, Psono, Grafana, Node-RED e consoles administrativos: URL, protocolo, callback, grupo, papel, tenant e conta break-glass.
- [ ] Para cada aplicação, executar login, logout, expiração, revogação, usuário desativado, MFA, retorno de callback inválido e IdP indisponível.
- [ ] Testar usuário `viewer`, `operator`, NOC/SOC e `platform_admin`; o backend, e não a UI, deve negar tenant/papel indevido.
- [ ] Reduzir superadmins por decisão explícita, sem excluir a única conta de recuperação.
- [ ] Salvar evidência sem cookies, claims nem tokens.

### Task 3.2: Tornar Psono um cofre operacional

**Files:**
- Modify: `docs/execution/psono-aiops-temporary-2026-08-31.md`
- Create: `docs/runbooks/psono-custodian-recovery.md`

- [ ] Formalizar Ricardo Esper e Ismael Araújo como os dois custodians; confirmar contatos fora da VPS.
- [ ] Exigir MFA dos custodians e gerar códigos de recuperação; guardar cópias offline separadas, com procedimento de dupla custódia.
- [ ] Validar SMTP e fluxo de recuperação com conta de teste; não registrar senha temporária em evidência.
- [ ] Executar restore independente por cada custodian e validar auditoria, sem tornar a AIOps dependência única.
- [ ] Decidir promoção dedicada do Psono somente após o PoC passar esses testes; documentar compartilhamento de VPS apenas se risco e isolamento forem aceitos formalmente.

### Task 3.3: Migrar e rotacionar segredos

**Files:**
- Create: `docs/security/secret-migration-register.md`
- Create: `infra/secrets/README.md`

- [ ] Gerar/reunir chaves SOPS/age com recuperação por dois responsáveis; versionar apenas material cifrado e identificadores, nunca valores.
- [ ] Migrar um consumidor por vez: registrar identificador, colocar o novo segredo no cofre, alterar o consumidor, testar, revogar o anterior e registrar data/owner.
- [ ] Prioridade: credenciais de VPS, S3/Restic, Contabo, GLPI API, Zabbix API, Authentik, SMTP e integrações.
- [ ] Rodar secret scan no checkout, imagens e evidências antes de encerrar a migração.

**Exit evidence:** G2 `PASS`, MFA e revogação comprovadas, dois custodians recuperam o cofre e nenhum segredo válido está em Git/VPS fora do padrão.

---

## Phase 4 — Zabbix definitivo e qualidade de coleta

**Owner de execução:** ness. operações. **Aprovação de corte:** Ricardo Esper. **Rollback:** origem `144.91.72.202` intacta.

### Task 4.1: Z-M1 — revalidar e obter baseline atual

**Files:**
- Create: `docs/execution/evidence/zabbix-zm1-YYYY-MM-DD.md`

- [ ] Em leitura, comparar origem e `zbx-prd-01` (`169.58.234.9`): versão, DB, hosts, itens, triggers, templates, proxies, filas, NVPS, busy, ações, mídias e conectores.
- [ ] Confirmar backup Zabbix `COMPLETED`, SHA-256, `gzip -t`, `restic check` e restore isolado mais recente.
- [ ] Fixar uma baseline única; números anteriores ficam históricos e não são usados para aceite.

### Task 4.2: Z-M2 e Z-M3 — restaurar e manter isolado

**Files:**
- Create: `docs/execution/evidence/zabbix-zm2-zm3-YYYY-MM-DD.md`

- [ ] Gerar backup reversível do banco do destino antes de importar qualquer snapshot.
- [ ] Restaurar a baseline validada no destino e validar `dbversion`, tabelas, hosts, itens, triggers e tempo de importação.
- [ ] Manter `zabbix-server` mascarado/inativo; confirmar ausência de listener 10051, proxies/agentes, ações, mídias e conectores ativos.
- [ ] Testar que nenhuma notificação ou coleta produtiva pode sair do destino em UAT.

### Task 4.3: Z-M4 — homologar SSO e piloto Cavan — Matriz

**Files:**
- Modify: `docs/execution/zabbix-data-quality-and-visibility-plan-2026-08-28.md`
- Create: `docs/execution/evidence/zabbix-cavan-pilot-YYYY-MM-DD.md`

- [ ] Reexecutar HTTPS/SAML/MFA/break-glass com contas nominais e perfil mínimo.
- [ ] Preparar no máximo 5 ativos Cavan — Matriz: FortiGate, links, switches e VMs; exportar estado anterior antes de cada escrita.
- [ ] Aplicar/validar tags obrigatórias: `tenant`, `site`, `service`, `environment`, `technology`, `scope`, `owner`, `role`, `criticality`.
- [ ] Corrigir templates por causa: FortiGate/links, Aruba/switches, VMware/storage e Windows/Linux; usar `Unlink`, nunca `Unlink and clear`.
- [ ] Classificar todos os `unsupported` do piloto em incompatibilidade, credencial, conectividade ou exceção aceita. Meta: 100% tags/template/owner no piloto e redução >=70% do ruído FortiGate relevante.
- [ ] Validar agente/SNMP, item→trigger→recovery, proxy perdido e alerta sintético com canais reais desligados.
- [ ] Observar 24–72 h; só então ampliar para 25 hosts. Qualquer dupla coleta, backlog crescente ou alerta indevido aborta a onda.

### Task 4.4: Z-M5 — corte e observação

**Files:**
- Create: `docs/execution/zabbix-cutover-YYYY-MM-DD.md`
- Create: `docs/execution/evidence/zabbix-dplus1-dplus3-dplus7.md`

- [ ] Abrir mudança GLPI com janela, TTL DNS, snapshot final, contatos, critérios de abortar e retorno DNS/proxies para a origem.
- [ ] Obter GO formal depois de Z-M1–Z-M4 e G0/G1/G2 aprovados.
- [ ] Cortar DNS; ativar somente a coleta/proxies aprovados em ondas; manter ações/mídias reais bloqueadas no primeiro smoke test.
- [ ] Validar API, UI, SSO, dados, fila, NVPS, busy, backups e ausência de dupla coleta.
- [ ] Registrar D+1, D+3 e D+7. Manter origem preservada por 7–14 dias; só depois decidir desativação controlada.

### Task 4.5: Zabbix — visibilidade e branding após estabilidade

- [ ] Criar dashboards separados: NOC/SOC, qualidade de coleta, governança/SLO, cliente e engenharia.
- [ ] Criar mapas Cavan por conectividade e serviços; coordenadas/endereço/criticidade vêm do GLPI.
- [ ] Validar recorte de tenant, responsividade e reconciliação dos números contra a fonte.
- [ ] Aplicar logo, favicon e CSS por camada suportada/reversível, sem alterar core nem bloquear upgrade; testar reversão e upgrade.

**Exit evidence:** Z-M5 aprovado, origem preservada até observação, coleta correta, alertas qualificados e painéis baseados em dados confiáveis.

---

## Phase 5 — GLPI: ITSM, catálogo e inventário

### Task 5.1: Resolver a API de máquina

**Files:**
- Create: `docs/execution/evidence/glpi-machine-api-YYYY-MM-DD.md`

- [ ] Definir rota/política compatível com SSO para service identity de menor privilégio; não contornar autenticação humana nem reutilizar superadmin.
- [ ] Guardar token da aplicação e usuário técnico no cofre; testar criação de sessão, leitura limitada e revogação.
- [ ] Confirmar que chamadas sem escopo, token revogado e tenant errado recebem negação segura.

### Task 5.2: Fechar a fundação de serviços

- [ ] Validar entidades por cliente, perfis, grupos de atribuição, categorias, catálogo, projetos, tarefas e runbooks.
- [ ] Corrigir SLAs que calculam duração zero a partir da unidade contratual aprovada; registrar fonte contratual antes de ativar.
- [ ] Para cada serviço do piloto, preencher ativo, local, owner, contrato, serviço e criticidade.

### Task 5.3: Inventário Cavan e GLPI Agent

- [ ] Reconciliar os ativos Cavan com Zabbix usando identificador externo estável; preservar histórico e evitar duplicatas.
- [ ] Ativar GLPI Agent somente em 5 ativos do piloto, validar inventário, privacidade, consumo e remoção.
- [ ] Ampliar após 24–72 h sem duplicação; o agente coleta inventário técnico, não substitui o catálogo de serviço.

### Task 5.4: Aceitar o ciclo de ticket

- [ ] Criar ticket sintético autorizado pelo Hub/API e pela UI; validar atribuição, atualização, SLA, vínculo de ativo, resolução e fechamento.
- [ ] Confirmar trilha auditável e idempotência em três replays.
- [ ] Registrar resultado no gate GLPI; só então liberar escrita Hub → GLPI.

**Exit evidence:** GLPI é sistema de registro de ativos/tickets do piloto e suporta a integração sem bypass de SSO.

---

## Phase 6 — Hub: runtime, dados e interface confiável

### Task 6.1: Executar o Compose real em ambiente alvo

**Files:**
- Modify: Compose/healthchecks existentes
- Create: `docs/execution/evidence/hub-runtime-uat-YYYY-MM-DD.md`

- [ ] Subir PostgreSQL, Redis, API, Celery, frontend e proxy com release G0 aprovada.
- [ ] Verificar migrations em base nova e existente; registrar compatibilidade de rollback.
- [ ] Derrubar deliberadamente Redis, PostgreSQL, um worker e GLPI simulado/indisponível; `/ready` deve falhar fechado e recuperar após retorno.
- [ ] Monitorar fila, locks, retries, memória Redis, evictions, latência, erros, TLS e frontend.

### Task 6.2: Garantir contrato de dados e segurança

- [ ] Executar UAT de API e SSE para `viewer`, `operator`, NOC/SOC e `platform_admin` em tenant autorizado e tenant negado.
- [ ] Confirmar que logout/revogação encerra sessões HTTP e streams; que uma falha de fonte mantém último sucesso e mostra erro/frescor.
- [ ] Confirmar que dashboard, ativos, Contabo e incidentes não apresentam mocks ou dados estáticos como reais.
- [ ] Manter Contabo API em leitura: inventário, estado e capacidade somente para `platform_admin` no backend.

### Task 6.3: PWA operacional

- [ ] Entregar jornada móvel de NOC/SOC: login, incidentes, ACK, ticket associado, fonte/frescor e notificação apenas quando a jornada for aprovada.
- [ ] Testar offline/retorno, token expirado, API indisponível e permissão negada; cache não pode exibir dado antigo como atual.
- [ ] Aplicar branding ness. e acessibilidade após a jornada passar.

**Exit evidence:** G3 `PASS`, runtime recuperável, RBAC efetivo e UI sem estados falsos.

---

## Phase 7 — G4: aceitar o MVP integrado

### Task 7.1: Executar o ensaio ponta a ponta

**Files:**
- Create: `docs/execution/evidence/mvp-zabbix-hub-glpi-uat-YYYY-MM-DD.md`
- Create: `docs/execution/gates/phase-4-integrated-mvp.md`

- [ ] Com ações externas desligadas, emitir evento sintético autorizado no host piloto Zabbix.
- [ ] Confirmar um evento de origem, um incidente tenant-scoped, um ticket GLPI e IDs cruzados auditáveis.
- [ ] Reenviar o evento três vezes, simular timeout GLPI e reiniciar worker; confirmar um único incidente/ticket e recuperação posterior.
- [ ] Emitir recuperação e confirmar transição de estado/encerramento conforme política.
- [ ] Repetir com tenant/papel errado; confirmar negação em API, stream e UI.
- [ ] Não liberar automações, canais reais, RMM, WhatsApp ou portal de cliente nesta etapa.

### Task 7.2: Aceite operacional

- [ ] Revisar G0, G1, G2, Z-M5, GLPI e G3 antes de marcar G4.
- [ ] Observar a operação D+1, D+3 e D+7; cada período exige backup atual, fila saudável, erro visível e zero incidente/ticket duplicado crítico.
- [ ] Registrar riscos residuais, owner e prazo; Ricardo aprova ou rejeita o go-live NOC/ITSM.

**Exit evidence:** G4 `PASS`; MVP Zabbix → Hub → GLPI aceito e reversível.

---

## Phase 8 — AIOps assistido, sem remediação autônoma

### Task 8.1: Formalizar o contrato operacional

- [ ] Definir schema versionado para alerta, incidente, enriquecimento, decisão e pós-incidente; incluir `tenant_id`, `source_event_id`, severidade, frescor, evidência e auditoria.
- [ ] Classificar entrada por severidade/tenant com fallback humano; sinal sem tenant vai para quarentena.
- [ ] Medir duplicidade, latência, tamanho/profundidade de fila, falha, custo de LLM e taxa de intervenção.

### Task 8.2: Implementar assistência controlada

- [ ] Produzir sugestão de RCA e runbook com contexto sanitizado, identidade persistida e botão de aprovação explícita.
- [ ] Testar que Gemini/MISP nunca recebem segredo, PII não necessária nem dados de outro tenant; limitar quota/custo e registrar apenas metadados seguros.
- [ ] Integrar Atera/Datto somente após contrato idempotente e aprovação de jornada; RocketCyber fica fora do escopo.

### Task 8.3: Migrar orquestração

- [ ] Inventariar fluxos n8n; para cada fluxo criar equivalente Node-RED em modo paralelo, com entrada/saída/rollback documentados.
- [ ] Comparar resultados por fluxo, promover um por vez e desativar origem somente após aceite.
- [ ] Evolution/WhatsApp só entra em uma jornada testada, com opt-in, rate limit, auditoria e aprovação humana.

**Exit evidence:** automação apenas sugere ou executa jornadas expressamente autorizadas, auditáveis e reversíveis.

---

## Phase 9 — Wazuh, Google Workspace e escala SecOps

### Task 9.1: Aprovar arquitetura e capacidade antes de comprar

- [ ] Atualizar BOM Contabo com topologia hub-spoke, CPU/RAM por papel, rede privada, backup e crescimento 100 → 500 → 1.000 → 5.000 endpoints; disco é dimensionado separadamente.
- [ ] Registrar quais VPS existentes são reaproveitáveis e quais são dedicadas; Hostinger é fallback/histórico, não dependência de produção.
- [ ] Submeter BOM, custo mensal e retenção para aprovação antes de provisionar.

### Task 9.2: Piloto isolado

- [ ] Implantar hub e spoke(s) em rede/credenciais segregadas; configurar RBAC, TLS, backup, restore e monitoramento antes de agentes.
- [ ] Onboard 50–100 endpoints Cavan, uma unidade lógica; medir EPS/APS, CPU, memória, fila, retenção e overhead de agente.
- [ ] Testar perda de spoke, queda de rede, endpoint removido, tentativa cross-tenant e restore.

### Task 9.3: Google Workspace em leitura mínima

- [ ] Usar conta superadmin somente para consentimento inicial; criar identidade delegada de menor privilégio no cofre e registrar escopos aprovados.
- [ ] Ingerir auditoria mínima em leitura; não habilitar Alert Center inicialmente.
- [ ] Normalizar no mesmo contrato de incidente, mantendo origem, frescor, tenant e deduplicação.

### Task 9.4: Escalar somente por faixa aprovada

- [ ] Promover 100 → 500 → 1.000 → 5.000 endpoints somente após estabilidade da faixa anterior no período definido.
- [ ] Recalcular BOM/custo e capacidade em cada promoção; falha retorna à faixa anterior, sem expansão automática.

**Exit evidence:** G5 `PASS`, Wazuh recuperável, isolado, medido e integrado sem expor payload bruto.

---

## Phase 10 — experiência, governança e operação sustentada

### Task 10.1: Dashboards e portal executivo

- [ ] Criar visões NOC/SOC, sustentação, governança, executivo e cliente a partir de fontes aceitas; cada cartão informa fonte, timestamp e estado.
- [ ] Incluir saúde de serviços, status de projetos, governança, infraestrutura, sustentação, segurança e capacidade; separar cliente/tenant rigorosamente.
- [ ] Não usar dados mockados em telas operacionais. Módulos futuros aparecem como planejados/indisponíveis.

### Task 10.2: Runbooks e ownership

- [ ] Para cada serviço crítico, publicar runbook operacional (não repositório oficial de políticas), owner, dependências, SLO, alerta, backup, RPO/RTO, rollback e calendário de revisão.
- [ ] Vincular runbook e mudanças ao GLPI; registrar on-call e escalonamento sem expor contatos particulares.
- [ ] Testar cada runbook por pessoa que não o escreveu e corrigir lacunas.

### Task 10.3: Aplicar branding transversal

Referência consolidada de cobertura: [customização transversal ness.](2026-10-12-ness-branding-cross-product-plan.md). Aplicar a todos os produtos deste roteiro por mecanismo suportado. A elaboração dessa matriz foi somente planejamento; execução pelo modelo autor está vedada por instrução humana.

- [ ] Aplicar fundação visual em Hub/PWA, Authentik, Psono, Zabbix, GLPI, Grafana e consoles operacionais com camadas suportadas e reversíveis.
- [ ] Validar pt-BR, contraste, responsividade, densidade, navegação, empty/error states, favicon e títulos sem duplicação.
- [ ] Testar atualização de cada produto para garantir que branding não altera core nem bloqueia patch de segurança.

### Task 10.4: Fechar o programa

- [ ] Conferir todos os IDs R/B/I/S/Z/G/H/X/A/W/E deste roteiro contra evidência atual.
- [ ] Registrar pendência residual com risco, owner, data e aceite explícito; item sem evidência permanece aberto.
- [ ] Publicar estágio final e tag de release; o programa só é considerado operacional depois dos ciclos D+1/D+3/D+7 aplicáveis.

## Definition of Done

- [ ] G0, G1, G2, Z-M5, G3, G4 e, quando Wazuh entrar, G5 possuem evidência datada e `PASS`.
- [ ] Zabbix definitivo fornece telemetria qualificada; GLPI é o registro de ativos/tickets; Hub trata um incidente por tenant sem duplicação.
- [ ] Cofre possui dois custodians, MFA, recuperação e rotação rastreável; não há segredo válido no Git.
- [ ] Todo serviço crítico tem backup/restore, RPO/RTO medidos, rollback, owner, SLO, alerta e runbook testado.
- [ ] Painéis e PWA mostram somente dados reais ou explicitamente indisponíveis/planejados.
- [ ] Wazuh/Workspace somente são incluídos como operacional após o piloto e a escala passarem seus próprios gates.

## Referências de execução detalhada

- Fase de release: `docs/superpowers/plans/2026-09-18-phase-0-recovery-release-baseline.md`
- Identidade e tenant: `docs/superpowers/plans/2026-09-18-phase-1-identity-tenant-controls.md`
- Zabbix e GLPI: `docs/superpowers/plans/2026-09-18-phase-2-zabbix-glpi-operations.md`
- Runtime Hub: `docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md`
- Dashboard operacional: `docs/superpowers/plans/2026-09-18-phase-4-dashboard-operational-truth.md`
- Aceite integrado: `docs/superpowers/plans/2026-09-18-phase-6-integrated-acceptance.md`
- Wazuh: `docs/superpowers/plans/2026-09-18-wazuh-4147-production-rollout.md` e `docs/superpowers/plans/2026-09-18-wazuh-security-signal-ingestion.md`
