# GLPI no ness.OS — plano completo de implementação

> **Para o executor:** usar `superpowers:executing-plans`, tarefa por tarefa, e `ponytail:ponytail` em nível full para programação. Ler as instruções atuais do repositório. Este documento é somente planejamento: o usuário determinou **não executar com o modelo que o escreveu**. A implementação deve começar após a troca de modelo e uma instrução humana de retomada. Heartbeats antigos não substituem essa restrição.

**Objetivo:** entregar o GLPI como ITSM e CMDB canônicos do ness.OS, com isolamento verificável, inventário reconciliado, fluxo de incidentes confiável, operação utilizável, identidade ness. e sustentação documentada.

**Arquitetura:** GLPI é responsável por ativos, catálogo, contratos e tickets. O Hub correlaciona eventos, mantém a referência canônica e apresenta o estado operacional. Authentik autentica pessoas; perfis e entidades GLPI autorizam suas ações. Integrações usam identidades próprias e APIs normais; personalizações utilizam configuração ou extensão suportada, sem alterações no core.

**Stack existente:** GLPI/PHP/MariaDB em containers, Authentik, backend Python/FastAPI/SQLAlchemy/Celery/Redis, GLPI Agent, Zabbix, Compose e GitHub. Versão GLPI registrada: 11.0.8; confirmar imagem e digest antes de escolher uma atualização.

**Especificação e evidências:** `docs/adr/0002-glpi-canonical-itsm.md`, `docs/architecture/ness-os-official-architecture.md`, `docs/execution/glpi-next-delivery-2026-10-12.md`, `docs/execution/glpi-operating-foundation-2026-09-08.md`, `docs/execution/project-stage-2026-10-12.md` e requisitos do usuário neste chat. Evidência operacional antiga não se transforma em aceite atual por estar citada aqui.

## 1. Limites e decisões fixadas

- GLPI é o cadastro mestre. Hub, Zabbix e RMM preservam referências; não criam cadastros mestres concorrentes.
- Primeiro aceite funcional: plataforma interna ness., 5–10 ativos, canais Hub e GLPI. Reconciliação posterior cobre todo o inventário existente por ondas de até cinco alterações de ativos.
- Cavan é uma empresa; Matriz e unidades fabris são localidades. Não remodelar entidades existentes sem mapa de impactos aprovado. Alupar tem o primeiro lote técnico já preparado.
- Conta Hub 94/perfil 12 permanecem intactos. Conta de manutenção 106 está desativada após falha de isolamento; perfil 13 e associação 125 não provam segurança de entidade.
- Não usar SQL de configuração/autenticação ou `callAsSystem` para contornar direitos. Consultas de diagnóstico somente leitura devem ser limitadas e sanitizadas.
- Nenhum segredo em Git, chat, email, argumentos de processos, fixtures ou evidências públicas. Credenciais temporárias serão revogadas no encerramento da mudança.
- SLA contratual exige duração, unidade, calendário, fuso, pausas e cobertura aprovados. Não preencher dados fictícios para eliminar lacunas.
- Notificações externas permanecem desligadas. Não excluir ou encerrar chamados reais em massa.
- Não comprar recursos, instalar plugins pagos ou ampliar infraestrutura sem aprovação específica de custo.
- Zabbix origem continua coletor único; destino permanece isolado. Este plano não autoriza corte DNS ou ativação de coleta.
- RPO alvo 24 horas; RTO alvo 4 horas. Reutilizar ensaios válidos; repetir recuperação somente se a mudança afetar recuperabilidade, se a prova estiver inválida ou no gate de liberação aplicável.
- Alertas brutos: 90 dias; incidentes qualificados: 12 meses. Não aplicar automaticamente essa retenção aos tickets, anexos, contratos ou auditoria GLPI: definir a política própria de preservação antes de qualquer expurgo.
- Cada alteração produtiva exige ticket de mudança aceito, executor, janela, export anterior, precondição, readback e rollback. Ticket operacional 75426 não substitui a aprovação de uma Change recusada pela API.
- Janela antiga termina em 13/10/2026 11:47:35 BRT. O próximo executor deve conferir horário e autorização vigente antes de mutações remotas; não reutilizar credenciais expiradas.

## 2. Estado de partida: comprovado, histórico e pendente

Números abaixo são amostras de 12–13/10/2026 registradas no documento de execução, não consulta ao ambiente feita durante a elaboração deste plano.

| Área | Evidência registrada | Consequência para execução |
|---|---|---|
| Base GLPI | 12 entidades; 103 computadores; 153 equipamentos de rede | Inventariar regras e dependências antes de criar ou mover registros |
| Tickets | 76.119 não excluídos na amostra; 76.118 novos; zero duplicatas pelo marcador completo | Investigar crescimento e ciclo de vida; marcador único não elimina duplicação semântica |
| Hub | 255 mapeamentos verificados; 115 incidentes sem ticket na amostra | Classificar pendentes por idade, política e retry antes de reprocessar |
| Vínculos | 645 incidentes sem ativo nos hosts 10983/10984/10987; mais um sintético 10978 | Aplicar lote restrito e reparar referências elegíveis, preservando sintético |
| Coleta | Sete agentes sem contato nas 24 horas anteriores à amostra | Causa desconhecida; não declarar agentes mortos por contagem |
| SLA | Oito definições incompletas; sem atribuição na amostra | Dependência contratual real |
| Identidade técnica | Perfil 13 corrigido para Computer READ+CREATE+DELETE; conta 106 desativada | Isolamento falhou ao selecionar entidade descendente 5 e ler ativo real |
| Identidade humana | Login administrativo demonstrado; SSO via proxy 12; OIDC 8 não efetivo | Homologar revogação, MFA e autorização por perfil; não trocar protocolo incidentalmente |
| Personalização | Branding Authentik aplicado; GLPI ainda sem entrega visual aceita | Implementar experiência GLPI própria em camada reversível |
| Testes | Infra 96 + 3 subtests; suíte geral teve 72 falhas por ausência de pywebpush | Reproduzir ambiente de dependências antes de afirmar CI verde |

## 3. Responsabilidades e governança dos dados

| Dado/ação | Fonte de verdade | Regra de integração |
|---|---|---|
| Cliente e entidade | Cadastro aprovado no GLPI e mapa de tenants versionado | Ausência ou conflito bloqueia escrita; não inferir pelo nome/IP |
| Ativo físico/VM | GLPI e inventário autenticado | Serial/UUID validado; nome/IP só ajudam a investigar |
| Host monitorado | ID Zabbix + marcador estável | Vários testes WAN podem apontar ao mesmo equipamento; não forçar relação física 1:1 |
| Evento e recovery | ID de evento/origem no Hub | Persistir antes de processar; replay mantém identidade |
| Trabalho humano e solução | Ticket GLPI | Atualização humana tem precedência; recovery não apaga diagnóstico ou fecha investigação automaticamente |
| SLA/contrato | Condição aprovada pelo responsável contratual | Sem contrato válido, mostrar “não definido”, nunca “cumprido” |
| Permissão | Backend, perfis e fronteira de acesso verificada | Ocultar menu não autoriza nem protege dados |

Ricardo responde pelas decisões de negócio e aceite. Ismael é referência técnica operacional conforme decisões anteriores; confirmar substituto no handover. O agente executor produz artefatos, testes e evidências. Decisões dependentes de pessoas entram em issues existentes ou novas somente quando necessário, com instrução objetiva por email conforme autorização já dada.

## 4. Ordem de entrega e critérios de passagem

| Entrega | Tarefas | Saída verificável | Dependência |
|---|---|---|---|
| E1 — acesso e processamento seguros | T01–T04 | Escopo fail-closed, contenção do gap nativo, retry e idempotência comprovados | Nenhuma escrita ampla antes de T02/T03 |
| E2 — inventário e atendimento | T05–T09 | Lote piloto, reconciliação, agentes, catálogo e backlog classificado | E1 para aplicação; preparação pode ocorrer antes |
| E3 — experiência ness. | T10–T11 | Jornadas e painéis utilizáveis com dados rastreáveis | Pode ser preparada em paralelo local com E1/E2 |
| E4 — liberação e sustentação | T12–T14 | Release, canário, UAT, runbooks e observação | Gates técnicos e humanos aplicáveis |

O executor pode avançar uma tarefa independente se outra depender de humano. Nunca marcar o gate bloqueado como aprovado. Permissão para paralelismo não significa autorização automática para disparar agentes adicionais; seguir instruções da sessão.

## 5. Foco obrigatório de revisão

1. HTTP 200 com entidade efetiva diferente da solicitada deve bloquear operação: T02/T03.
2. Criação de ticket confirmada remotamente, seguida de timeout local, deve convergir sem duplicata: T04.
3. Ativo mudou de entidade entre dry-run e aplicação: abortar sem mover ou vincular dados: T05/T06.
4. Recovery chega antes do evento ou depois de solução humana: preservar causalidade e trabalho humano: T04/T08.
5. Interface mostra número plausível a partir de fonte atrasada ou inacessível: explicitar frescor/erro e escopo: T11/T14.

## 6. Contratos dos artefatos novos

Os caminhos marcados “criar” abaixo são propostos; não existem por este plano. Arquivos existentes foram localizados no repositório. Antes de alterar código, ler o arquivo inteiro e preservar convenções atuais.

- `config/glpi/ness-access-policy-v1.json`: schema_version, revision, identidades por ID, allowed_entity_ids explícitos, operações autorizadas. Nenhum segredo ou herança implícita.
- `config/glpi/ness-ticket-policy-v1.json`: revision, critérios de elegibilidade, severidade, grupo/categoria por IDs validados, transições permitidas e política de recovery. Campos contratuais ausentes não recebem defaults inventados.
- `config/glpi/ness-reconciliation-policy-v1.json`: fontes, tipos permitidos, mapa de entidade, identidade canônica, exclusões justificadas, precedência e limites de lote.
- Manifesto de lote protegido: change_id, policy_revision, source_revision, expected_before_digest, operações, IDs alvo, entidade, estado anterior e compensação. Digest é de configuração sanitizada, nunca de segredo.
- Relatório sanitizado de execução: started_at_utc, finished_at_utc, commit, ambiente, change_id, tarefa, escopo, resultado PASS/FAIL/BLOCKED, contadores, IDs de evidência protegida, rollback_status. Sem payload bruto ou dados pessoais.
- Comandos novos de mutação usam dry-run por padrão, `--apply` explícito e manifesto com precondição. Rollback só compensa objetos criados/alterados pela execução; conflito com edição posterior exige revisão.

## T01 — congelar o escopo executável e preparar ambiente de teste

**Arquivos:** ler documentos citados; criar `docs/execution/glpi-delivery-ledger-2026-10-12.md` e `config/glpi/ness-release-inventory.json`; revisar `app/backend/requirements.txt`, `app/backend/pyproject.toml`, `docker-compose.yml`, `app/docker-compose.yml` e `app/docker-compose.tickets.yml`.

**Entrada:** estado Git/runtime e evidências existentes. **Saída:** inventário de release sem segredos e ledger por tarefa; não criar outra stack produtiva.

- [ ] Registrar branch, commit, alterações locais, imagem/digest efetivo, Compose efetivo, plugins/versões/licenças, volumes, cron e rota Authentik. Consultar somente lacunas; não repetir auditoria inteira.
- [ ] Selecionar banco de testes isolado e fixtures sanitizadas, com envio externo e conectores desligados. Nunca apontar teste destrutivo a produção.
- [ ] Instalar dependências conforme arquivo do projeto em ambiente limpo; esclarecer `pywebpush` ausente sem desativar testes ou mascarar imports.
- [ ] Executar do diretório `app/backend`: `python -m pytest -q tests/test_alert_glpi_idempotency.py tests/test_resolution_sync.py tests/test_glpi_readiness.py`. Registrar resultado real e falhas anteriores.
- [ ] Preencher ledger com evidências reaproveitadas, alterações que exigem nova prova e bloqueios. Commit somente dessa preparação.

**Aceite:** baseline reproduzível e testes executáveis; nenhuma alegação de saúde produtiva derivada deles.

## T02 — proteger o consumidor contra seleção incorreta de entidade

**Modificar:** `app/backend/app/integrations/glpi.py`, `app/backend/app/config.py` e consumidores de `change_active_entity`. **Criar:** política de acesso acima e `app/backend/tests/test_glpi_entity_scope.py`.

**Interface proposta:** `async verify_entity_scope(self, entity_id: int, allowed_entity_ids: frozenset[int]) -> None`; lança `PermissionError` antes da operação se qualquer prova falhar. Preservar assinatura pública atual de `change_active_entity(entity_id)` e integrar a política validada no cliente, sem obrigar migração simultânea dos consumidores.

- [ ] Criar testes: entidade 1 autorizada passa; 5/8 fora da allowlist negadas; seleção retorna True/200 mas entidade continua anterior nega; seleção ativa múltiplas entidades ou recursão nega; resposta ausente/malformada nega; token revogado nega.
- [ ] Testar duas operações concorrentes para entidades distintas: nenhuma sessão mutável compartilhada pode trocar o escopo da outra. Testar encerramento em sucesso, exceção e cancelamento.
- [ ] Executar testes e observar falhas pelas condições atuais, não por dependência ausente.
- [ ] Implementar validação da política, direitos/grants relevantes, resposta normalizada de `getActiveEntities` e entidade do recurso/payload. Esquema desconhecido falha fechado. Usar sessão exclusiva por operação ou serialização explícita por sessão.
- [ ] Aplicar a mesma checagem a criação, leitura, busca, atualização, vínculo de ativo, acompanhamento e resolução. Paginação não pode trazer dados de outro escopo.
- [ ] Rodar `python -m pytest -q tests/test_glpi_entity_scope.py tests/test_alert_glpi_idempotency.py tests/test_resolution_sync.py tests/test_glpi_readiness.py`; revisar diffs e commitar.

**Aceite:** nenhum consumidor próprio escreve/lê fora da política; teste prova zero chamada de mutação após negação. **Limite:** guard no Hub não corrige acesso direto à API nativa com o token.

## T03 — resolver o requisito de isolamento da manutenção

**Criar:** `docs/adr/0020-glpi-maintenance-entity-boundary.md` (se número já existir, usar próximo livre), `infra/tests/test-glpi-maintenance-boundary.py`; atualizar política de acesso e issue 74.

**Entrada:** reprodução documentada conta 106/entidades 1 e 5; não repetir em produção. **Saída:** decisão suportada e fronteira de acesso comprovada, ou bloqueio explícito que impede reativação.

- [ ] Reproduzir em ambiente isolado com entidades e ativos sintéticos; documentar se “não recursivo” é restrição de seleção ou apenas visualização no contrato nativo. Conferir documentação/fonte da versão candidata.
- [ ] Avaliar primeiro mecanismo suportado de restrição no servidor que cubra leitura, busca, exportação, subitens e escrita. Hooks de criação sozinhos não satisfazem esse requisito.
- [ ] Se não houver mecanismo completo, preparar decisão concreta entre gateway privado restrito e identidade de operação com escopo descendente explicitamente aprovado. Recomendação deste plano: gateway restrito para automação; não expandir silenciosamente o escopo aprovado.
- [ ] Para gateway, exigir: token upstream só no serviço, cliente não recebe token/sessão upstream, rota nativa bloqueada para essa identidade/rede, allowlist de endpoints, entidade determinada no servidor, validação de todo objeto aninhado, negação de URLs/IDs arbitrários, bulk e métodos não permitidos. Reusar infraestrutura existente; não criar serviço genérico de proxy.
- [ ] Prototipar e testar o caminho escolhido isoladamente. Casos: troca para descendente, seleção all, IDOR de Computer/Ticket/anexo, busca, exportação, batch, path encoding, sessão reaproveitada e tentativa direta de API upstream. Todos devem negar dados não autorizados.
- [ ] Registrar escolha, arquivos exatos e contrato da solução no ADR antes de implementação produtiva. Mudança de escopo de acesso ou topologia de entidades requer decisão humana; manter tarefa BLOCKED se essa for a única alternativa.
- [ ] Só reativar 106 pelo caminho normal após readback de direitos mínimos e testes diretos negativos aprovados; gerar/rotacionar credencial apenas se necessário. Registrar revogação da credencial antiga e fechar sessões.

**Aceite:** acesso permitido à entidade 1 e negação efetiva às demais por todos os percursos expostos. Uma opção de arquitetura ainda não provada não é aprovação. **Rollback:** desativar 106 e remover somente a nova rota; Hub 94 permanece operacional.

## T04 — interromper duplicação operacional e garantir entrega idempotente

**Modificar:** `app/backend/app/workers/alerts.py`, `app/backend/app/workers/resolution.py`, `app/backend/app/integrations/glpi.py`; modelo/migration apenas se faltar persistência necessária, em `app/backend/app/models/models.py` e mecanismo de migration existente. **Testes:** `test_alert_glpi_idempotency.py`, `test_resolution_sync.py`. **Criar:** política de tickets e `infra/scripts/glpi-backlog-classify.py`.

**Contrato:** chave de entrega inclui tenant verificado, origem e identificador persistente do evento/incidente. Preservar fingerprints históricos; não recalcular marcadores existentes por mudança de algoritmo.

- [ ] Classificar os incidentes sem ticket em: ainda dentro da latência, retry agendado, bloqueado por autorização, exclusão de política, erro permanente ou estado inconsistente. Relatório agregado com cursor; nada de replay amplo.
- [ ] Correlacionar crescimento de tickets por entidade/trigger/host/episódio e estado de recovery; distinguir reenvio idêntico de flapping e eventos distintos. Criar amostra reproduzível das maiores causas.
- [ ] Fixar testes: três replays e concorrência geram um ticket; timeout após POST encontra ticket antes de novo POST; falha de worker após criação converge; lock Redis perdido não permite duplicata; ticket de outro tenant com marcador semelhante nunca é reutilizado.
- [ ] Testar recovery anterior ao evento, replay após solução humana e erro 401/403 versus 429/5xx. 401/403 não entram em loop infinito; 429/5xx têm backoff limitado e dead-letter visível. Sem perda do evento persistido.
- [ ] Implementar somente lacunas identificadas nos mecanismos existentes. Se o GLPI não impõe unicidade do marcador, tratar explicitamente a corrida entre busca e criação; não considerar lock efêmero suficiente sem teste de falha.
- [ ] Rodar suíte focada e ensaio isolado com falhas injetadas. Provar um incidente/um ticket e auditoria da recuperação.
- [ ] Preparar canário interno com política conservadora: preservar eventos brutos, qualificar incidente antes do ticket, quarentenar tenant desconhecido. Agrupamento entre eventos distintos precisa de regra versionada e evidência; não descartar alertas por volume.

**Aceite:** entrega repetível e recuperável sem duplicata por mesma identidade, backlog novo explicável e falhas visíveis. **Rollback:** voltar política/release; preservar filas e chaves já persistidas para não duplicar no retorno.

## T05 — concluir os três ativos e os vínculos pendentes

**Reusar/revisar:** `infra/scripts/glpi-hub-complete-inventory.php`, `infra/scripts/glpi-hub-link-tickets.php`, `infra/scripts/hub-glpi-integrity-check.py`, `app/backend/app/integrations/cmdb_sync.py`. **Criar:** `infra/scripts/glpi-asset-wave.py`, `infra/tests/test-glpi-asset-wave.py`; ampliar `infra/tests/test-cmdb-scope.py`.

**Interface:** aplicador recebe manifesto com hostids, entidade e tipo, `--dry-run`/`--apply`/`--rollback <run-id>`. Lote inicial exclusivo 10983, 10984, 10987; 10978 excluído como sintético. Padrão é dry-run e no máximo cinco IDs.

- [ ] Exportar referências anteriores e verificar que permanecem ausentes no GLPI por marcador em todos os tipos relevantes, incluindo excluídos; qualquer ambiguidade bloqueia o registro.
- [ ] Criar testes de repetição, falha no segundo ativo, terceiro já existente, entidade alterada após plano, tipo conflitante, item excluído e lote maior que cinco.
- [ ] Implementar via API normal o caminho de criação; corrigir comentário com data fixa e registrar identificador monitorado sem inventar serial físico. Reusar lógica segura dos scripts existentes, sem executar contexto privilegiado implícito.
- [ ] Após T03, criar lote e conferir ID, tipo e entidade por GET. Persistir apenas IDs comprovados e executar `cmdb_sync.reconcile(apply=True, hostids=[...])` pelo runtime da release candidata.
- [ ] Reparar os vínculos históricos elegíveis em páginas limitadas: validar ticket, fingerprint, tenant, item e ausência de vínculo conflitante antes de cada inclusão; registrar cursor para retomada.
- [ ] Readback cruzado Hub/GLPI e segunda aplicação sem novas criações/vínculos. A contagem histórica 645 serve como referência; fechar pela lista de IDs elegíveis, não pela contagem isolada.

**Aceite:** três ativos ou referências canônicas inequívocas, todos os vínculos elegíveis corretos e idempotência. **Rollback:** desfazer somente vínculos da execução e excluir logicamente ativo recém-criado somente se não recebeu novas referências; conflitos exigem compensação assistida, sem purge.

## T06 — reconciliar todo o inventário existente

**Modificar:** `cmdb_sync.py` e `infra/scripts/hub-glpi-integrity-check.py`. **Criar:** política de reconciliação e `infra/tests/test-glpi-reconciliation-policy.py`.

- [ ] Gerar manifesto completo dos 262 hosts reais e 63 protótipos registrados, classificando físico, VM, serviço/teste sintético, desativado e desconhecido. Revalidar só mudanças desde o último registro.
- [ ] Conferir as 255 referências existentes por delta; investigar quatro marcadores GLPI extras históricos. Não presumir que diferença de contagens significa ativos físicos ausentes.
- [ ] Definir para cada identidade monitorada: ativo canônico, entidade verificada, fonte e motivo de exclusão quando aplicável. Preservar 10877 desativado e protótipos fora da contagem de dispositivos.
- [ ] Validar serial/UUID autoritativo antes de consolidar equipamentos com vários testes ou converter NetworkEquipment em Computer. Exportar relações, histórico, tickets e contratos antes de qualquer conversão; conversão ambígua fica pendente.
- [ ] Testar identidade igual em tenants distintos, troca de IP/nome, VM clonada, reinstalação de agente e inventário atrasado. Nunca fundir apenas por IP/nome ou sobrescrever campo mestre com leitura antiga.
- [ ] Aplicar lotes de até cinco registros com checkpoint; abortar onda em conflito de entidade ou identidade. Não automatizar exclusões globais.

**Aceite:** 100% das identidades existentes classificadas como mapeadas ou exceção explícita com responsável/prazo; zero vínculo conhecido cruzando tenant e zero duplicata canônica não explicada. Completude de owner/local/contrato é medida separada de identidade e não recebe valores fictícios.

## T07 — tornar o inventário dos agentes confiável

**Reusar:** `infra/scripts/glpi-inventory-readiness-report.sh`, `glpi-inventory-security-audit.sh`. **Criar:** `docs/operations/glpi-agent-rollout.md`, `config/glpi/ness-agent-rollout.json`.

- [ ] Diagnosticar sete registros sem contato: serviço instalado, endpoint/TLS, autenticação de inventário, tarefa agendada, conectividade e regra de entidade. Relatório agregado sem serial/IP público.
- [ ] Confirmar entrada de inventário autenticada e regras que não permitam ao cliente declarar arbitrariamente outro tenant. Testar inventário forjado e associação errada em isolamento.
- [ ] Pilotar cinco ativos internos: instalação pelo RMM existente, primeiro inventário, identidade estável, contato seguinte, consumo, campos coletados, privacidade e desinstalação.
- [ ] Propor inventário diário; marcar atrasado após 48 horas e desconhecido antes da primeira entrega. Para ativos intermitentes, registrar exceção explícita; essa política não altera SLA contratual.
- [ ] Expandir em ondas aprovadas, com relatório por sistema/cliente e retorno ao pacote anterior. Desabilitar deployment remoto de software e tarefas adicionais não necessárias ao inventário inicial.

**Aceite:** piloto completo e autenticado, sem duplicatas; cobertura/frescor mensuráveis por entidade. Expansão termina quando todo ativo elegível tiver inventário recente ou exceção identificada.

## T08 — configurar atendimento, catálogo e ciclo de vida

**Reusar:** `config/glpi/ness-operations-foundation-v1.json`, `ness-os-foundation-v1.yaml`, `infra/scripts/glpi-operations-foundation.php`, módulos `glpi_project_manifest.py` e `glpi_runbook_categories.py`. **Criar:** `docs/operations/glpi-service-operation.md` e matriz de perfis em `config/glpi/ness-role-matrix.json`.

- [ ] Comparar catálogo, categorias, grupos, projeto e runbooks atuais com manifesto; atualizar por ID/chave estável. Não recriar a fundação de setembro.
- [ ] Mapear jornadas de solicitante, técnico, NOC/SOC, gestor e administrador: criar, atribuir, acompanhar, pendência com motivo, solução, validação, reabertura e encerramento. Definir quem pode cada transição.
- [ ] Configurar formulários de incidente e requisição com serviço, entidade, impacto, urgência e ativo quando aplicável; campos desconhecidos continuam explícitos. Aplicar matriz de prioridade reproduzível.
- [ ] Rotear tickets qualificados para grupo validado por serviço/entidade; não escolher pessoa por default global. Serviço sem grupo entra em fila de triagem visível.
- [ ] Recovery acrescenta evidência; solução automática fica limitada a casos sintéticos ou política expressamente aprovada. Ticket com trabalho humano segue validação prevista.
- [ ] Implementar contratos/SLA somente com condições aprovadas: TTO/TTR, calendário, feriados, fuso, pausa, retomada e escalonamento. Testar virada de dia, fim de semana e pendência sem contar pausa indevida.
- [ ] Homologar toda jornada com contas de perfis distintos e entidade permitida/negada, incluindo anexos, artigos e pesquisa global.

**Aceite:** equipe consegue executar atendimento completo; nenhum prazo falso e nenhum acesso indevido. SLA pendente limita aceite contratual, mas não impede catálogo e fluxo interno.

## T09 — tratar o backlog com preservação de histórico

**Reusar:** relatório T04, integridade e sincronização de resolução existentes. **Criar:** `docs/operations/glpi-backlog-remediation.md` e manifestos protegidos por onda.

- [ ] Separar tickets em trabalho real, incidente ainda ativo, recovery não sincronizado, erro de integração, duplicata comprovada e caso sem evidência suficiente.
- [ ] Publicar quantidades, idade e causa por entidade sem conteúdo pessoal; priorizar falhas de integração que continuam gerando entradas.
- [ ] Reparar referências ausentes e reprocessar entregas elegíveis por fluxo idempotente, com cursor, limite e readback.
- [ ] Apresentar lote pequeno de transições propostas com prova de origem/recovery e política aplicável. Encerramento real em massa permanece fora da autorização; obter decisão de operação para cada política de saneamento.
- [ ] Manter audit trail e vínculo entre duplicata e ticket canônico. Não apagar duplicata para melhorar indicador.

**Aceite:** novos tickets seguem ciclo correto e 100% do backlog está classificado ou em fila com motivo explícito; redução numérica só conta quando decorrente de tratamento legítimo.

## T10 — personalização ness. e jornadas de uso

**Cobertura ampliada:** aplicar a linha GLPI da [matriz transversal ness.](2026-10-12-ness-branding-cross-product-plan.md), incluindo catálogo, base de conhecimento, relatórios, exportações e prévias de emails. Canais externos continuam desligados; máximo de personalização suportada, sem modificar core.

**Criar:** `docs/operations/glpi-ness-experience.md`, `config/glpi/ness-branding-manifest.json`, `infra/tests/inspect-glpi-branding.cjs`. Implementar assets/CSS somente no caminho de extensão confirmado por inventário T01; registrar esse caminho no manifesto antes de editar.

- [ ] Ler skill `ness-branding` e referências visuais; reutilizar logo aprovado, fonte Montserrat Medium 500 e ponto #00ade8. Marca em preto/branco, sem itálico e sem descritor anexado ao logo. Preservar nome técnico ness.OS nos identificadores existentes; marca visual segue ness.
- [ ] Escolher mecanismo suportado já disponível, com compatibilidade GLPI 11 e licença conhecida. Se plugin compatível inexistir, preparar extensão mínima em UAT; não contratar plugin nem editar core para obter aparência.
- [ ] Desenhar desktop e móvel para três entradas: solicitante (abrir/acompanhar), técnico (minha fila/serviço/ativo) e gestor (volume/idade/cobertura). Manter administração acessível só a perfis autorizados.
- [ ] Usar largura útil da tela, navegação lateral clara, cabeçalho compacto e título único. Evitar repetição de “ness.” no logo, título e subtítulo da mesma região. Padronizar pt-BR, datas BRT, mensagens acionáveis e estados vazios.
- [ ] Aplicar grid 8px, foco visível, contraste WCAG AA, alvos de toque 48px, reduced-motion e navegação por teclado. Tabelas extensas podem ter rolagem local identificável; página não pode vazar horizontalmente.
- [ ] Testar 390px e 1440px, zoom 200%, login, listagem, criação/edição de ticket, anexos, ativo, pesquisa, painel e logout. Checar ações de salvar/excluir e ausência de controles cobertos pelo tema.
- [ ] Testar desativação da camada de branding e atualização de produto em ambiente isolado. Exportar antes/depois e registrar hashes de assets sem segredo.

**Aceite:** jornadas completas com marca consistente e legibilidade, sem regressão funcional. **Rollback:** desativar extensão/restaurar configuração visual anterior, sem restaurar banco inteiro.

## T11 — painéis operacionais e visibilidade no Hub

**Modificar conforme necessidade:** `app/backend/app/integrations/glpi_readiness.py`, `pipeline_health.py`, `app/backend/app/services/operational_status.py`; localizar componente frontend consumidor antes de alterar. **Criar:** `config/glpi/ness-dashboard-manifest.json` e testes de contrato associados aos módulos alterados.

- [ ] Definir indicadores com fórmula, fonte, escopo, timestamp e drill-down: novos/atribuídos/pendentes, idade p50/p95, criação versus solução, sem responsável, sem ativo, cobertura/frescor de inventário, erro/retry/latência da integração e SLA quando configurado.
- [ ] Separar saúde técnica de API da saúde do atendimento. API pronta não transforma 76 mil chamados novos em operação saudável.
- [ ] Implementar painéis NOC/SOC, service desk, gestor e cliente com filtros coerentes e autorização no backend. Não carregar dados globais no navegador e apenas ocultar linhas.
- [ ] Testar fonte indisponível, cache vencido, zero real, sem dados, dados parciais e perfil sem autorização. Não exibir verde nem percentual de SLA quando denominador/fonte não estiver válido.
- [ ] Conferir números de amostra com consultas nativas na mesma janela temporal e entidade; documentar diferença de atualização entre Hub e GLPI.

**Aceite:** cada indicador permite investigar a origem e mostra limitação/frescor; usuário de cliente não acessa agregados de outro cliente.

## T12 — runtime, plugins e atualização controlada

**Modificar somente Compose efetivo identificado em T01. Criar:** `docs/operations/glpi-release-runbook.md` e `config/glpi/ness-plugin-compatibility.json`.

- [ ] Inventariar sete plugins sinalizados na interface: versão, uso, dependência, licença e compatibilidade. Não atualizar todos por causa do aviso.
- [ ] Selecionar versão GLPI mantida a partir das fontes oficiais no dia da execução e registrar digest. A condição de entidades observada também existia na fonte 11.0.11 consultada; upgrade sozinho não é correção aceita de T03.
- [ ] Validar pacote oficial, PHP/extensões, MariaDB, diretórios persistentes, TLS, reverse proxy, trust de headers, CSRF/cookies, limites de upload e acesso a arquivos. Não publicar MariaDB ou API de manutenção.
- [ ] Verificar ações automáticas em modo CLI, agendador único, permissões, logs e atraso; executar somente tarefa controlada após ler efeitos. Não iniciar fila de emails histórica.
- [ ] Medir páginas e consultas principais com volume realista; usar EXPLAIN/telemetria antes de índices ou tuning. Meta inicial de aceite em ambiente representativo: p95 até 2s para leitura API simples e até 3s para listagem de 50 tickets, documentando rede e concorrência; resultado pior abre correção, não altera número silenciosamente.
- [ ] Ensaiar upgrade/migration e retorno isolados com dados compatíveis. Rollback que exija banco anterior precisa reconciliar escritas ocorridas depois do snapshot; não prometer reversão sem perda por simples troca de imagem.
- [ ] Revalidar recuperação apenas para dados/chaves/plugins afetados pela release. Confirmar último backup válido e disponibilidade do artefato de retorno para a promoção, sem repetir restore histórico por rotina.

**Aceite:** versão e plugins compatíveis, cron comprovado, performance medida, plano de reversão aplicável. Atualização ainda não ensaiada não entra no mesmo corte da integração por conveniência.

## T13 — release, canário e homologação ponta a ponta

**Criar:** `docs/execution/glpi-release-acceptance.md`; ampliar verificadores existentes somente onde faltar teste. **Entrada:** tarefas técnicas aplicáveis aprovadas e bloqueios humanos explicitados.

- [ ] Rodar suites focadas e CI do repositório com dependências corretas; lint/tipos/configuração/secret scan pertinentes. Guardar commit e versão de políticas usados; não chamar o CI de aprovado por um subconjunto.
- [ ] Registrar mudança, janela, owner, pacote anterior, critérios de aborto e plano de reversão. Congelar apenas o escopo alterado e evitar interromper ingestão sem persistência.
- [ ] Promover canário interno 5–10 ativos: evento sintético → incidente → ticket → atribuição → acompanhamento → solução/recovery conforme política → atualização Hub. Notificações externas desligadas.
- [ ] Repetir evento três vezes e provocar timeout GLPI e reinício de worker no cenário controlado: exigir um ticket, zero perda, retry rastreável e recuperação.
- [ ] Testar token revogado, usuário desativado, viewer tentando escrever, cliente cruzado, sessão expirada, anexo indevido, MFA nominal e logout. Usuário humano confirma somente a parte que requer seu fator.
- [ ] Abort criteria: qualquer acesso cruzado, duplicata do mesmo evento, perda de entrega, alteração fora de escopo ou falha impeditiva de login/ticket. Pausar apenas componente da nova release e executar rollback documentado.
- [ ] Expandir por entidades/ondas depois do canário. Registrar aceites independentes: técnico interno, segurança humana, contrato/SLA e operação de cliente. Não declarar liberação integral com algum obrigatório pendente.

**Aceite de liberação:** fluxo produtivo verificado, escopo correto, suporte e rollback disponíveis; assinatura de Ricardo conforme governança do projeto. **Observação:** D+1/D+3/D+7 contam a partir desta promoção real.

## T14 — sustentação e encerramento

**Atualizar:** runbooks existentes no manifesto de operações, guia de implantação e ledger. **Criar:** `docs/operations/glpi-ness-implementation-guide.md`, consolidando procedimentos aprovados, sem duplicar segredos ou instruções divergentes.

- [ ] Documentar URLs, papéis, entidades, instalação/release, incidentes, fila/retry, agentes, catálogo, SLA, dashboards, branding, backup, recuperação, rollback e escalonamento. Incluir sintomas e comandos verificados por procedimento.
- [ ] Vincular artigos/projeto/mudanças existentes no GLPI pelos seus IDs, após checar permissões. Validar execução de um runbook por pessoa diferente do autor.
- [ ] Observar D+1/D+3/D+7: falhas de acesso, duplicidade, atraso, inventário, crescimento do backlog, cron, latência e backup; investigar desvio, sem refazer ensaios aprovados quando nada mudou.
- [ ] Revogar tokens temporários de manutenção, encerrar sessões e confirmar identidade de integração permanente com menor privilégio. Remover cópias temporárias autorizadas, preservando evidências sem segredo.
- [ ] Consolidar commit/release, mudanças, issues residuais, responsável e prazo. Dependência humana sem resposta permanece pendente; não encerrar issue só por haver documentação.
- [ ] Emitir relatório final separando GLPI liberado, operação observada, aceites humanos e itens fora de escopo. Encerrar automação de implementação quando concluída; monitoração recorrente deve ter objetivo próprio.

**Aceite final:** todos os critérios obrigatórios abaixo comprovados ou exceções formalmente aprovadas que não invalidem segurança/funcionalidade.

## 7. Matriz objetiva de conclusão

| Critério | Prova exigida | Impede qual liberação |
|---|---|---|
| Isolamento de entidades | Testes diretos e via Hub, inclusive descendentes e anexos | Escrita da manutenção e exposição a clientes |
| Idempotência e recuperação | Replay/concorrência/timeout/restart com ticket único | Integração produtiva nova |
| Inventário | Mapeamento ou exceção de toda identidade, piloto agentes aprovado | Aceite de CMDB completa |
| Fluxo de atendimento | Jornada por perfil e auditoria de transições | Operação do service desk |
| SLA | Contrato/unidade/calendário e cálculo testados | Aceite contratual, não preparação interna |
| Identidade humana | Login, MFA, revogação, logout e recuperação nominal | G2 e acesso privilegiado integral |
| Experiência | Desktop/móvel/teclado, títulos únicos e branding reversível | Aceite de UX |
| Continuidade | Backup válido, recuperação pertinente, release/rollback identificados | Promoção produtiva |
| Sustentação | Runbook exercitado, owner/substituto, observações reais | Encerramento operacional |

## 8. Ritmo e estimativa de trabalho

Estimativas de esforço técnico, não promessa de prazo de parede nem aprovação automática: T01 1–2h; T02 2–4h; T03 4–8h para diagnóstico/protótipo mais a implementação da alternativa comprovada; T04 4–8h; T05 2–4h; T06 4–8h conforme ambiguidades; T07 3–6h para piloto; T08/T09 4–8h cada; T10 4–8h; T11 3–6h; T12 3–6h se compatibilidade aprovada; T13 3–6h; T14 2–4h de documentação mais sete dias de observação. Reestimar após T01 e T03; não prometer concluir tudo numa janela de quatro horas.

Primeiro bloco de execução: T01 e T02, testes de T03 em isolamento, diagnóstico T04 e desenho T10. Segundo bloco: fechar fronteira T03, canário T04, lote T05 e configuração T08. Terceiro: inventário amplo/agentes, backlog, UI/painéis e release. Nenhum bloco precisa esperar SLA para escrever testes, preparar interface ou classificar dados.

Atualizar usuário em até 60 segundos durante trabalho ativo com tarefa, resultado e próximo passo. No ledger, cada tarefa usa NOT_STARTED / IN_PROGRESS / BLOCKED / VERIFIED / RELEASED; registrar evidência e próxima ação. Não atribuir porcentagem global baseada em número de arquivos ou commits.

## 9. Fontes técnicas e limitações conhecidas

- API oficial GLPI 11: https://github.com/glpi-project/glpi/blob/11.0/bugfixes/apirest.md — Context7 consultado na elaboração; documenta getActiveEntities/changeActiveEntities/getActiveProfile. Resposta 200 não substitui verificação de estado efetivo.
- Seleção de entidades: https://github.com/glpi-project/glpi/blob/11.0.11/src/Session.php — causa registrada na evidência local; conferir versão efetiva antes de adaptar solução.
- Hooks oficiais: https://github.com/glpi-project/glpi/blob/11.0/bugfixes/src/Glpi/Plugin/Hooks.php — hooks de escrita não demonstram cobertura de leitura/exportação.
- GLPI Agent: documentação oficial a consultar com Context7 ao fixar pacote e parâmetros da onda; nenhuma versão de agente foi escolhida por este plano.
- Skill de planejamento utilizada: `superpowers:writing-plans`; branding segue `ness-branding`. Na retomada, consultar documentação atual das APIs/CLI e confirmar comandos na versão instalada.

## 10. Handoff ao próximo modelo

1. Ler este plano e o fim de `docs/execution/glpi-next-delivery-2026-10-12.md` antes de qualquer acesso remoto.
2. Confirmar que o usuário trocou o modelo e pediu execução; este plano não é uma instrução para autoexecutar no modelo autor.
3. Conferir janela/credenciais atuais. Não reativar 106 por instrução antiga de heartbeat.
4. Iniciar T01/T02. Usar T03 como gate real para criação do lote; continuar tarefas locais independentes enquanto a fronteira for resolvida.
5. Implementar uma tarefa, verificar proporcionalmente, atualizar ledger e seguir. Não repetir importação Zabbix, branding Authentik ou restore já comprovado.
6. Este documento não alterou produção, permissões, tokens, ativos, tickets ou agendamentos. Todas as caixas permanecem por executar.
