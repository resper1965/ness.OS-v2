# Zabbix — encerramento completo do capítulo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para executar tarefa por tarefa. Não pedir confirmação entre tarefas; parar somente em operação sem autorização, destrutiva ou dependência indispensável.

**Goal:** Entregar o Zabbix definitivo com todos os ativos existentes reconciliados, coleta qualificada, identidade, painéis, marca, operação e retorno comprovados.

**Architecture:** A origem continua sendo a única coletora até o corte. A UAT recebe variantes e deltas reversíveis por API normal. Um registro completo por host e por protótipo governa as ondas; nenhuma amostra de cinco hosts representa aceite dos demais.

**Tech Stack:** Zabbix 7.0.27, MariaDB, Python/pytest, API JSON-RPC, SNMP, Authentik/SAML, systemd, Cloudflare DNS e GitHub.

**Spec:** `docs/execution/project-stage-2026-10-12.md`, `docs/execution/zabbix-production-window-2026-10-12.md`, `docs/execution/zabbix-data-quality-and-visibility-plan-2026-08-28.md` e plano completo aprovado no chat.

## Global Constraints

- Escopo inicial: 262 hosts reais (261 ativos, um desativado), 63 protótipos LLD. Reconciliar entradas/saídas novas sem omissão; protótipo não conta como dispositivo.
- Janela autorizada até 13/10/2026 11:47:35 BRT. A meta anterior acabou; esta ordem autoriza continuar o trabalho, não falsificar os gates.
- Ondas de até cinco; host 10877 permanece desativado. Nunca `templates_clear`, apagar histórico, SQL de configuração ou elevar a conta Hub.
- Nenhum segredo no Git/chat/e-mail. Sessão UAT temporária, login/API/logout normal; arquivos operacionais root-only 0600.
- Nada de restore, dump, marca ou ensaio já aprovado repetido sem mudança. Snapshot final é somente a migração final, não um novo teste de backup.
- Coleta da origem permanece ativa. Coleta UAT/DNS/canais externos só com gates, freeze, GO e rollback. G2 em issue não significa PASS.
- RPO ≤24h; RTO ≤4h. Unsupported <0,5% dos itens habilitados dos hosts reais no corte, e redução ≥70% dos unsupported relevantes FortiGate; ambos os critérios devem passar. Exceção aceita é visível e não remove erro do denominador.
- Sem owner/tenant/criticidade inventados. Lacuna gera issue com responsável e instrução; seguir trabalho independente.
- Definição final exige produção e observação D+1/D+3/D+7; preparação/UAT não são conclusão.

## Review Focus

1. Protótipos e hosts descobertos: flags 0/4 são ativos reais; flags 2 são protótipos. Falhar para ID repetido/flag inesperada.
2. Host desativado: preservar status e histórico; nenhuma onda habilita automaticamente.
3. Filtro LLD: retenção não pode excluir itens perdidos; observar disable/re-enable e IDs no retorno.
4. Replay após refresh: aplicar somente sobre before esperado ou after idêntico; divergência aborta sem sobrescrever.
5. Snapshot/sem fonte: ausência de erro não é saúde; mostrar timestamp, fonte, frescor e indisponibilidade, inclusive em móvel e perfil cliente.

## Arquivos e execução

Reutilizar `infra/scripts/zabbix-quality-wave.py`, scripts de SAML, NOC, branding e corte existentes. Não reimplementar o servidor/API/backup. Novos módulos: registro completo de cobertura e transformação de variante LLD. Evidências brutas ficam protegidas no host; commits levam somente campos sanitizados, plano, deltas e testes.

### Task 1: Registro obrigatório de todos os ativos

**Files:** Create `infra/scripts/zabbix-asset-register.py`; Test `infra/tests/test-zabbix-asset-register.py`; Create `config/zabbix/asset-register-20261012.json`.

**Interfaces:** `build_register(rows: list[dict], observed_at: str) -> dict`. Entrada por host: hostid, flags, status, name, templates, tags, item_count, unsupported_count, error_categories. Saída: assets, prototypes, waves, totals; cada asset contém estado pendente, lacunas e onda; não contém IP, macro, serial ou erro bruto.

- [x] Testar exclusão de protótipos do total real, preservação de desativado, cobertura exata sem ID duplicado, ondas ≤5 e recusa de entrada inválida; dados sem itens não podem sair como saudáveis.
- [x] Executar `python3 -m pytest -q infra/tests/test-zabbix-asset-register.py`; observar RED por função ausente.
- [x] Implementar registro sem inferir identidade pelo nome: estado disabled_preserved, unconfigured, needs_remediation ou assessment_required. Ausência de unsupported não gera accepted.
- [x] Fazer uma leitura sanitizada da origem, contar itens flags 0/4 (não protótipos de itens), categorias de erro sem texto bruto e tags/templates reais; gerar registro completo. Totais precisam reconciliar SQL de origem e IDs únicos.
- [x] Executar testes e registrar todos os IDs nas ondas. Esperado inicialmente 262 assets, 63 prototypes, 53 ondas; divergência abre investigação, não força o número.
- [ ] Commit/push e atualizar ledger. Nenhum host fica sem linha nem protótipo é esquecido.

### Task 2: Perfil Cavan de links sem exclusão LLD

**Files:** Modify `infra/scripts/zabbix-snmp-variant.py`; Test `infra/tests/test-zabbix-snmp-variant.py`; Create delta/evidência protegida `fortigate-link-transition-20261012.json`.

**Interfaces:** `clone_link_transition(document: dict) -> dict`; nome `FortiGate by SNMP - UAT link transition`; manter timeout original; somente net.if.discovery muda lifetime_type para DELETE_NEVER no export (API: 1). UUIDs/refências renovados; template raiz intocado.

- [ ] Testar clone não muta origem, mantém timeout, muda só retenção da regra correta e recusa export ambíguo/hosts. Rodar RED; implementar; rodar GREEN.
- [ ] Exportar 10604 por API UAT normal; criar candidato; importcompare permite apenas adições; importar createMissing=true/updateExisting=false. Confirmar raiz idêntica e variante sem hosts.
- [ ] Exportar configuração e IDs de itens/triggers de 10873/10874; ensaiar vínculo sem templates_clear em um host por vez, preservar IDs/chaves/status e retornar ao template anterior. Não repetir ensaio da variante 5s: este ensaio é da variante nova.
- [ ] Preparar macros ^wan$ em 10873 e ^lan3$ em 10874; não aplicá-las antes de retenção NEVER confirmada. Conservar appliance 10977 completo, host 10877 desativado.
- [ ] Observar LLD somente em coletor autorizado único; antes/depois de dois ciclos medir interfaces desejadas, recursos preservados e desativados; rollback exige redescoberta/reativação, não apenas troca de template. Sem isso marcar prepared, não accepted.
- [ ] Métricas de appliance duplicadas: inventariar dependências e painel antes de desativar no perfil de link. Não esconder divisão por zero nem fundir históricos.

### Task 3: Corrigir causas-raiz SNMP e do piloto

**Files:** Existing `infra/tests/verify-zabbix-snmp-variant-live.py`, scripts de variantes/ondas; deltas por host em `config/zabbix/` e ledger.

- [ ] Investigar masters 85756/85977 antes dos 992 dependentes; variante 5s já existe, não editar template global.
- [ ] Medir resposta/custo por coletor único, comparar mesmas chaves/hosts habilitados, duas janelas de coleta; timeout pode permanecer erro, não aceitar por configuração aplicada.
- [ ] Piloto 10873/10874/10878/10885: dependências, suporte do modelo/OID, intervalos, disponibilidade e recuperação. 10877 é inventário desativado, não alvo de coleta.
- [ ] Divisão por zero: confirmar capacidade real e aplicabilidade. Sem capacidade confiável manter erro/unknown com causa, nunca substituir por 0/100% saúde.
- [ ] Teste negativo e rollback por delta; redução ≥70% FortiGate relevante; publicar contagem anterior/posterior, janela e IDs. Commit por onda.

### Task 4: Executar o registro inteiro, não só Cavan

**Files:** asset-register e `infra/scripts/zabbix-quality-wave.py`; Create `infra/scripts/zabbix-freshness.py`, Test `infra/tests/test-zabbix-freshness.py`; Create `config/zabbix/quality-waves/` com deltas sanitizados; ledger por host.

**Interfaces:** `summarize_freshness(metrics: list[dict], observed_epoch: int) -> dict` consome itemid/delay/lastclock/state; intervalos positivos em segundos/s/m/h/d, sem macros/agenda presumida. Fresh exige clock>0, clock≤observação e idade≤3×intervalo. Relógio futuro, ausência, unsupported ou intervalo não resolvido são unknown; vazio é UNKNOWN. Resultado com fresh/stale/unknown e estado não equivale a disponibilidade ou aceite de saúde. Coletor lê somente pulsações agent.ping/icmpping/system.uptime e identifica esse escopo, não alega testar todos os serviços.

- [ ] Para cada onda: export before, verificar estado de origem e ambiente, causa, template atual e aplicabilidade comprovada; aplicar candidato UAT; verificar replay e rollback.
- [ ] Zero itens: os 14 hosts sinalizados precisam coleta real configurada ou exceção formal de ausência; a tag unconfigured não fecha o host. Sintético 10978 mantém trapper, não ganha template artificial.
- [ ] Agente Windows/Linux: erro de chave/contador resolve por versão/chave comprovada; autenticação/conectividade exige corrigir consumidor/transporte, não cálculo. VMware/storage: credencial/reachability/API e LLD; switches: modelo/OID/SNMP/bulk. HTTP: status/autorização/schema antes de JSONPath.
- [ ] Tags obrigatórias tenant/site/service/environment/technology/scope/owner/role/criticality vêm de cadastro confirmado; não deduzir dos nomes. Fonte e responsável registrados.
- [ ] Cada asset recebe resultado, evidência/horário, risco, rollback e issue residual. Cada protótipo recebe parent/rule/template e consistência LLD verificados. Sem outcome por ID, etapa incompleta.
- [ ] Medir unsupported <0,5%, amostras recentes ≤3×intervalo efetivo nos itens essenciais e disponibilidade correta; exceções contratuais explícitas. Não marcar accepted enquanto issue crítica ou ausência de coleta existir.

### Task 5: Painéis, mapas e acabamento para inventário completo

**Files:** `config/zabbix/`, `infra/tests/verify-zabbix-noc-browser.cjs`, `infra/tests/verify-zabbix-mobile-browser.cjs`, `infra/zabbix/modules/ness_mobile/`, branding/config existente.

- [ ] Preservar 405, 406/407 e deltas existentes. Construir visão qualidade (unsupported, sem coleta/template/tags, atraso) e capacidade (fila/NVPS/busy) sem fonte fictícia.
- [ ] Disponibilidade: mostrar denominador elegível e total cadastrado separadamente; 259 não representa automaticamente 261 hosts ativos.
- [ ] Mapas: vínculos/interface/site/criticidade do cadastro confirmado; sem coordenadas ou conexão inventadas. Compartilhar somente com grupo/tenant apropriado.
- [ ] Validar desktop e móvel com menu recolhido e widgets visíveis/clicáveis, pt-BR, contraste, marca nativa e títulos sem duplicação. Overflow=false não aprova móvel.
- [ ] API/UI com conta cliente não acessa outros tenants; renderização emergencial não substitui esse teste. Export/rollback e replay pós-refresh aprovados.

### Task 6: Identidade e readiness de promoção

**Files:** issues 51/71, scripts de SAML/probe e ledger de gates.

- [ ] Ismael/Ricardo homologam conta nominal, MFA, logout federado, sem grupo, revogado/desativado, expiração e callback inválido; instruções já corrigidas, não cobrar novamente sem mudança.
- [ ] Identidade técnica mínima e allowlist: positiva no piloto, negativa fora do escopo; token protegido e revogação. Não elevar conta Hub.
- [ ] G0/G1/G2: reusar evidências válidas; renovar somente o requisito expirado/alterado. Backup age ≤24h é leitura de manifesto, não motivo para dump de teste.
- [ ] Guardar gate por requisito com evidence timestamp, owner e PASS/FAIL; nenhum gate pode passar por issue aberta ou processo running.

### Task 7: Corte definitivo com retorno

**Files:** scripts existentes final-freeze-backup, cutover-enable-production, cloudflare-zabbix-dns-cutover, post-cutover-reconcile; checklist de corte.

- [ ] Exigir Tasks 1–6 aceitas e GO formal Ricardo; mudança/owner/janela/rollback. API Change403 não é aprovação.
- [ ] Freeze da única origem; snapshot final; restaurar somente esse snapshot final, reaplicar deltas verificados por before/after e validar paridade.
- [ ] DNS/proxies/allowlist; origem congelada antes de destino coletar. Inicialmente canais externos bloqueados. Provar ausência de dupla coleta e retorno de proxies/agentes.
- [ ] Smoke API/UI/SSO, itens essenciais, queue/NVPS/busy, backup atual e incidente/recovery controlado. Falha de coleta, acesso, paridade ou gates aborta: bloquear destino e voltar origem/DNS pelo checklist.
- [ ] Habilitar ações reais apenas após smoke aprovado e revisão de destinatários/tenant/canais; não liberar mídia em massa.

### Task 8: Operação e fechamento sem aceite fictício

**Files:** project-stage, registro por asset, runbooks e issues; evidências D+1/D+3/D+7.

- [ ] Observar D+1/D+3/D+7: filas, erros, perda de dados, backup RPO, capacidade e incidentes; agendar monitor apropriado dentro da autorização, sem polling repetitivo vazio.
- [ ] Guardar origem 7–14 dias; desativação posterior controlada e autorizada, não excluir agora.
- [ ] Publicar runbook por Zabbix/proxy com owner/substituto, SLO, escalonamento, restore e rollback; outra pessoa executa o runbook.
- [ ] Revisão independente do código/deltas; casos da Review Focus exercitados; GitHub/contextos atualizados, segredos fora do Git.
- [ ] Fechar capítulo somente com todos os IDs reconciliados, coleta e painéis aceitos, gates aprovados, corte produtivo e observação concluída. Se ação humana impedir, registrar bloqueio específico e continuar tarefas independentes; não declarar entrega completa.

## Rulings de execução

- O usuário pediu plano e execução até o fim: executar inline imediatamente, sem nova rodada de aprovação do plano.
- Continuar na branch de entrega existente e limpa, não abrir checkout duplicado ou reinstalar dependências; ledger próprio deste plano mantém BASE e testes.
- Contrato de aceite concilia as duas metas existentes: redução FortiGate ≥70% não dispensa unsupported global <0,5% no corte; mostrar ambos sem descontar exceções.
