# ness.OS — plano master de produção

> **Estado: execução autorizada e em andamento na branch de entrega.** Usar `ponytail:ponytail` full e `superpowers:executing-plans`; conferir o ledger e o último estágio antes de agir. A continuação do plano master está ativa, mas não renova janelas nem aprova gates.

**Objetivo:** entregar o ness.OS em produção, atendendo os clientes e ativos existentes com identidade, cofre, monitoração, inventário, atendimento, Hub, AIOps assistido e SecOps, experiência ness., evidência e retorno. O projeto não encerra na demonstração de um MVP.

**Arquitetura:** Authentik autentica; Psono guarda segredos; Zabbix monitora; GLPI é o cadastro mestre e ITSM; o Hub integra e apresenta; Node-RED orquestra jornadas autorizadas; Wazuh/Workspace compõem a entrega de segurança em produção. O backend impõe tenant e papel. Cada ferramenta mantém sua responsabilidade e fornece dados com origem, horário e qualidade.

**Stack existente:** FastAPI/PostgreSQL/Redis/Celery, React/Vite/PWA, Compose, Zabbix, GLPI, Authentik, Psono, Restic/Object Storage Contabo, Node-RED e Wazuh. Reusar implementação e infraestrutura; novas dependências precisam de necessidade concreta.

**Precedência:** este é o ponto único de entrada para sequência e escopo. Planos de produto abaixo fornecem o detalhe; documentos de execução fornecem evidência. Instrução humana mais recente prevalece. Caixas antigas desmarcadas não autorizam repetir uma entrega comprovada; caixas marcadas não dispensam conferir alteração posterior relevante.

## 1. Produto e decisões consolidadas

| Tema | Decisão vigente |
|---|---|
| Destino da entrega | Produção para todas as entidades e ativos existentes elegíveis; evento Zabbix → incidente Hub → ticket GLPI → acompanhamento e solução |
| Canário | 5–10 ativos internos ness. como teste inicial; aprovação aciona expansão por ondas, não encerra a entrega |
| Canais iniciais | Hub e GLPI; email, WhatsApp e push não entram no aceite inicial |
| Zabbix | Todos os ativos existentes no escopo; Cavan — Matriz continua piloto obrigatório antes do corte definitivo |
| Identidade | Authentik central; platform_admin somente Ismael Araujo, Rogerio Salerno e Ricardo Esper; MFA e autorização no backend |
| Cofre | Psono de produção em VPS dedicada; Ricardo e Ismael custodians, recuperação independente |
| Backup | Contabo Object Storage como única cópia externa inicial; risco de ausência de segunda cópia aceito, revisão trimestral |
| Continuidade | RPO ≤24h; RTO ≤4h. SLO inicial portal/API 99,5%; ingestão Zabbix 99,9% |
| Retenção | Alertas brutos 90 dias; incidentes qualificados 12 meses. Tickets/anexos/auditoria têm política própria antes de expurgo |
| Clientes | Cavan é uma empresa, com Matriz e unidades fabris; cadastro aprovado determina tenant/local/serviço |
| Segurança | Wazuh e Google Workspace dentro do programa de produção; ativação depende do núcleo seguro e gates próprios. Workspace leitura mínima, sem Alert Center |
| Automação | Assistida, com aprovação humana para ação privilegiada; RocketCyber fora do escopo |
| Infraestrutura | Contabo API somente leitura; novas compras/provisionamento exigem aprovação específica |
| Marca | Máxima customização útil e suportada ness., reversível, sem alterar core ou remover avisos/licenças |

A dedicação de VPS Psono está decidida; custo/provisionamento ainda exige aprovação operacional aplicável. “Risk accepted” de backup não permite afirmar conformidade integral 3-2-1.

### Escopo produtivo obrigatório

- Zabbix definitivo atende o inventário inteiro: referência inicial 262 hosts reais e 63 protótipos, com inclusões/saídas reconciliadas. Cada host recebe coleta aceita ou exceção formal; protótipo não vira dispositivo.
- GLPI/Hub cobrem todas as entidades existentes com ativos, serviços, filas, perfis e jornada de atendimento corretos. Exposição a cliente depende do teste negativo daquele tenant, não só de uma conta interna.
- Authentik atende aplicações efetivas; Psono dedicado e credenciais permanentes substituem acessos temporários de implantação.
- AIOps assistido e fluxos Node-RED aprovados funcionam sobre incidentes reais, mantendo atendimento manual disponível.
- Wazuh/Workspace têm produção própria: manifesto de endpoints elegíveis, capacidade aprovada, fontes autenticadas e observação por faixa. A meta arquitetural de 5.000 não representa 5.000 dispositivos existentes nem autoriza compra automática.
- Marca, suporte, dashboards e runbooks acompanham cada liberação. Produtos ainda bloqueados permanecem explicitamente pendentes no aceite global.

### Liberações contínuas, sem parada no canário

| Liberação | Conteúdo | Condição para a seguinte |
|---|---|---|
| P1 — núcleo produtivo | SSO/cofre aplicáveis, Zabbix definitivo, GLPI/Hub, jornada real para entidades existentes | Smoke e isolamento aprovados; observação segue em paralelo às tarefas independentes |
| P2 — operação assistida | RCA/runbooks, fluxos aprovados, portal/PWA e visões de operação/cliente | Jornadas, custo e autorização comprovados |
| P3 — segurança produtiva | Wazuh por faixa e Workspace leitura mínima | Capacidade, isolamento e recuperação aprovados |
| P4 — encerramento | Cobertura completa, marca, runbooks, observações e revogação temporária | Aceite global de produção |

Cada liberação coloca capacidade aceita em uso. Preparação da próxima começa assim que seus contratos estiverem disponíveis; sete dias de observação não criam uma pausa geral. Promoção que depende do requisito observado continua aguardando esse requisito.

## 2. Situação de partida

Registros existentes de 12/10, não nova auditoria produtiva desta compilação:

- Hub/AIOps tem promoção por imagens imutáveis e retorno ensaiado; G0 global ainda depende de CI e integração protegida do workflow.
- Zabbix origem segue coletor único; destino restaurado/isolation PASS. Registro: 262 hosts reais, 63 protótipos. Dois hosts SNMP tiveram 994 erros → 2; frota ainda 2,086% unsupported na última amostra.
- GLPI tem 255 referências cruzadas comprovadas, catálogo parcial e grande backlog. Três hosts sem ativo estão preparados; conta 106 desativada após acesso indevido a descendente. Não reativar por instrução antiga.
- Authentik tem branding público e SAML técnico aprovados; MFA nominal, recuperação, jornadas autenticadas e bindings Google permanecem pendentes.
- Psono tem recuperação histórica/atual registrada, mas dedicação, custodians e recuperação nominal não estão integralmente aceitos.
- Wazuh/Workspace e automações ampliadas não têm aceite produtivo completo. Módulo instalado/provider cadastrado não comprova operação.

Na retomada, usar o fim dos registros específicos para o último resultado. Não reler dumps, contar toda a base ou repetir restores para obter orientação.

## 3. Forma de trabalhar: ágil e verificável

1. Uma ferramenta principal por vez. Ordem preferida: acesso necessário → Zabbix → GLPI → Hub em produção → AIOps/segurança. Resolver pré-requisito de outra ferramenta sem abrir uma trilha inteira paralela.
2. Cada entrega curta contém problema, escopo, alteração mínima, verificação e retorno. Reusar scripts/componentes antes de criar novos.
3. Preparação local, testes isolados, documentação e desenho visual avançam com gates humanos pendentes. Produção dependente desses gates aguarda sua aprovação real.
4. Não repetir import, backup/restore, branding ou testes aprovados sem falha nova, alteração relevante ou necessidade do corte final. Idade do backup se verifica no manifesto.
5. Nova lógica de segurança, parser, retry ou migração recebe teste que reproduz a falha. Configuração simples recebe precondição/readback e prova operacional. Rodar somente checks afetados; ampliar diante de regressão.
6. Mudança produtiva tem identidade autorizada, ticket aceito, owner, janela, estado anterior e rollback. API 403 de Change não é aprovação; nunca contornar por SQL/callAsSystem.
7. Ondas de alterações de ativos: até cinco. Conflito de identidade/tenant aborta a onda; não inventar dados para fechar lacuna.
8. Dependência humana usa issue existente ou nova se necessário, com instrução por email conforme autorização dada. Não repetir cobrança. Continuar entregas independentes.
9. Um commit por entrega coerente, staging explícito e push após verificação. Nunca versionar segredo, dump, QR, token ou log pessoal.
10. Durante trabalho ativo, informar tarefa/resultado/próximo passo em até 60s. Registrar `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `VERIFIED` ou `RELEASED`, com evidência; nenhuma porcentagem baseada em quantidade de arquivos.

**Janela:** o usuário ampliou em 48 horas a autorização de mutações Zabbix;
novo limite adotado: **15/10/2026 11:47:35 BRT**. Conferir horário, token e
janela vigente antes de agir. O token temporário anterior expirou em 13/10;
esta extensão não renova credenciais nem aprova gates, GO, corte ou dupla
coleta. Não usar credenciais expiradas.

## 4. Fases e dependências

| Fase | Entrega | Entrada para promover | Saída |
|---|---|---|---|
| F0 | Retomada e release | Ordem de execução e checkout | G0 + evidência de continuidade aplicável |
| F1 | Authentik, tenant e cofre | F0 para mudanças produtivas | G2 por requisito e cofre operacional |
| F2 | Zabbix definitivo | G0/G1/G2 aplicáveis, qualidade e GO | Z-M5; uso produtivo após smoke |
| F3 | GLPI operacional | Release e fronteira de acesso correta | CMDB/atendimento/integridade aprovados |
| F4 | Hub e experiência de produção | Contratos F1/F2/F3 disponíveis | G3 |
| F5 | Operação integrada de todos os tenants | Gates anteriores obrigatórios aprovados | G4 por liberação, cobertura e observação |
| F6 | AIOps e orquestração assistidos | Contratos do núcleo disponíveis; promoção após gate dependente | Jornadas auditáveis com aprovação |
| F7 | Wazuh e Google Workspace | Núcleo seguro + capacidade/custo aprovados | G5 por faixa |
| F8 | Experiência completa e sustentação | Fontes aceitas por domínio | Produto completo, runbooks e revisão |

F1 pode bloquear apenas seu requisito dependente enquanto F2/F3/F4 são preparados isoladamente. Visuais são preparados junto de cada produto e promovidos com sua jornada funcional. F8 consolida a cobertura restante; não empurra toda a marca para o fim.

## F0 — retomar e fechar release sem ciclo repetitivo

**Detalhe:** planos de fase 0, contrato de release Hub e evidências de 12/10. **Artefatos:** manifesto de release existente, `docs/execution/gates/ness-os-gate-register.md` e estágio atual.

- [ ] Registrar commit/runtime/Compose/imagens/digests e classificar alterações locais. Resolver somente divergências reais, preservando trabalho do usuário.
- [ ] Completar CI limpo: testes/lint/tipos pertinentes, Compose, secret scan e SBOM. Falhas por dependência ausente, inclusive pywebpush registrada, são corrigidas na instalação reproduzível; não ignoradas.
- [ ] Confirmar canário/rollback existentes; repetir somente se release/configuração afetada mudou. Manifesto deve identificar exatamente o pacote promovido.
- [ ] Para cada serviço a alterar, conferir último backup completo dentro do RPO e prova de recuperação pertinente. Restore adicional só para requisito inválido/não comprovado ou mudança que afete recuperação.
- [ ] Fechar monitoramento de timer/COMPLETED/checksum/RPO e credenciais/prefixos isolados por produtor. Retenção de backups respeita capacidade aprovada; nenhuma poda destrutiva por default.
- [ ] Aprovar G0/G1 somente com evidência correspondente. Falha não impede preparação das fases seguintes, mas bloqueia a promoção dependente.

**Saída:** release identificável, retorno utilizável e continuidade observável. Não repetir a promoção já comprovada só para marcar uma tarefa antiga.

## F1 — identidade, isolamento e cofre

**Detalhe:** [Authentik](2026-10-12-authentik-fluid-delivery.md), plano fase 1 e roteiro geral seção de Psono/segredos.

- [ ] Corrigir bindings Google com interno/externo aprovado, matching verificado e testes negativos em fluxo candidato.
- [ ] Preparar recuperação e MFA administrativo; cada pessoa cadastra seu fator e prova uso/recuperação. Não exigir deny global antes de contingência.
- [ ] Homologar login/logout/expiração/revogação/usuário desativado por aplicação. Validar papel e tenant na API/SSE e autorização nativa GLPI/Zabbix/Grafana.
- [ ] Resolver identidade técnica mínima sem elevar conta Hub. G2 aberto em issues não equivale a PASS.
- [ ] Planejar/aprovar custo e promover Psono dedicado com TLS, hardening, SMTP, backup e monitoração; preservar origem temporária até retorno validado. Usar mecanismos da edição instalada, sem prometer SSO/licenciamento não confirmado.
- [ ] Formalizar Ricardo/Ismael, MFA e duas recuperações independentes, com contingência fora das VPS.
- [ ] SOPS/age e migração de segredos por consumidor: novo → teste → revogação anterior → identificador/owner/data. Prioridade VPS, backup/S3, Contabo, GLPI, Zabbix, Authentik, SMTP e integrações.

**Saída:** acesso central e cofre recuperáveis, permissões efetivas, segredo fora do Git. Cadastro nominal/contrato/custo necessários viram dependência explícita; o restante continua.

## F2 — concluir Zabbix

**Detalhe obrigatório:** [plano Zabbix enxuto](2026-10-12-zabbix-fluid-delivery.md), seis etapas; ledger anterior preserva histórico.

- [ ] Retomar pelo delta. Preservar restore aprovado, SNMP 10768/10769 e host 10877 desativado.
- [ ] Diagnosticar proxy/Windows via issue 73; obter UUID VMware autoritativo; corrigir cálculos e hosts sem coleta. Configurar por causa, em ondas de cinco, mantendo IDs/histórico.
- [ ] Registrar resultado de todos os hosts e consistência dos protótipos. Nenhum host some por não ter template ou por desconhecimento do owner.
- [ ] Provar frescor dos itens essenciais, redução FortiGate ≥70% e unsupported global <0,5%, sem retirar exceções do denominador. Cavan — Matriz permanece pré-requisito do corte.
- [ ] Fechar SSO nominal/MFA, acesso técnico e gates; GO formal de Ricardo.
- [ ] Fazer único freeze/snapshot final consistente, refresh necessário, replay dos deltas, mudança de endpoints/DNS e ativação do destino após origem parar. Smoke e retorno conforme checklist; nunca dupla coleta.
- [ ] Entregar painéis/mapas/mobile por perfil com dados atuais. Observar D+1/D+3/D+7; preservar origem 7–14 dias antes de desativação controlada.

**Saída:** destino único coletor produtivo; coleta e experiência aceitas. Operação liberada após smoke não é encerramento de observação.

## F3 — GLPI completo e fluido

**Detalhe obrigatório:** [plano GLPI](2026-10-12-glpi-ness-os-complete-delivery.md), T01–T14.

- [ ] T01–T03: ambiente reproduzível, guard de entidade efetiva e fronteira de acesso direta. Conta 106 continua desativada até teste negativo real passar; guard no Hub sozinho não resolve o acesso nativo.
- [ ] T04: investigar crescimento dos tickets e incidentes sem entrega, provar idempotência em replay/concorrência/timeout após criação. Persistência e auditoria antes da fila; falha de permissão não entra em retry infinito.
- [ ] T05/T06: aplicar lote 10983/10984/10987 e vínculos elegíveis após acesso correto; reconciliar todo inventário por identificador. Preservar sintéticos, duplicatas de representação e identidade física não comprovada.
- [ ] T07: diagnosticar sete agentes sem contato, pilotar cinco internos e expandir por ondas com autenticação, frescor e remoção testados.
- [ ] T08/T09: reusar catálogo/grupos/runbooks; configurar jornada solicitante/técnico/gestor, atribuição e solução. Classificar backlog e reparar integração; sem encerramento/exclusão em massa.
- [ ] SLA somente após condição contratual aprovada; pendência impede aceite contratual, não preparação do atendimento interno.
- [ ] T10–T14: experiência ness., painéis por perfil, plugins/upgrade compatíveis, canário e documentação. Não atualizar sete plugins em bloco porque existe aviso.

**Saída:** GLPI como mestre de ativos/tickets, fluxo utilizável e integração segura. Concluir pelo conjunto de registros elegíveis e jornada comprovada, não pela queda artificial de contagens.

## F4 — Hub, PWA e verdade operacional em produção

**Detalhe:** planos de fase 3/4 e contrato imutável Hub. **Arquivos centrais existentes:** `app/backend/app/integrations/glpi.py`, workers, serviço/schema operacional e `app/frontend/src/components/CoreDashboard.tsx`.

- [ ] Usar release por digest e migrations existentes, testando banco novo/existente e retorno compatível; não criar stack paralela produtiva.
- [ ] Provar dependências indisponíveis: PostgreSQL, Redis, worker e GLPI. Ready falha quando capacidade essencial falha; fila/retry/lock/eviction aparecem na operação.
- [ ] Validar HTTP/SSE por tenant/papel, revogação, expiração e logout. Backend determina privilégio.
- [ ] Corrigir mocks, timestamps fixos e health falso. Toda fonte informa sucesso anterior, frescor, erro e escopo; valor zero exige prova.
- [ ] Entregar visão geral, fontes, incidentes, detalhe/ACK, ativo/ticket, backup e infraestrutura Contabo somente leitura para platform_admin.
- [ ] PWA cobre login, incidente/ACK/ticket e falha; cache offline indica desatualização. Ícones aprovados e marca sem título duplicado.
- [ ] Testar jornadas desktop/móvel, acessibilidade e build; preservar componentes existentes, sem redesenho que substitua integração funcional.
- [ ] Preparar matriz de ativação de todas as entidades existentes: tenant, fontes, ativo/ticket, grupos, serviços, perfis, estado e evidência. Não publicar portal de cliente sem autorização efetiva comprovada.

**Saída G3:** runtime recuperável e produto utilizável com dados reais. Wazuh/Workspace ausentes continuam planned/unavailable.

## F5 — liberar operação integrada para todos os clientes existentes

**Detalhe:** plano de aceite integrado fase 6; testes do plano MVP de 27/09 são reaproveitados como canário. **Cobertura final:** todas as entidades e ativos existentes elegíveis; Hub/GLPI como canais. Canário de 5–10 ativos é apenas a primeira onda.

- [ ] Emitir evento sintético em ativo interno: um evento → um incidente do tenant correto → um ticket e ativo vinculados.
- [ ] Reenviar três vezes, provocar timeout GLPI e reiniciar worker de teste: manter identidade única, recuperação e auditoria.
- [ ] Emitir recovery; respeitar solução humana/política de encerramento. ACK não prova resolução técnica.
- [ ] Executar jornadas viewer/operator/NOC/SOC/platform_admin, negativa cruzada de tenant e interfaces desktop/móvel.
- [ ] Após canário aprovado, expandir imediatamente pelas entidades da matriz F4, começando Cavan — Matriz e seguindo o cadastro autorizado. Manter lotes de alterações até cinco ativos e checkpoints por tenant; não exigir novo desenho ou novo ciclo completo de backup por lote.
- [ ] Por entidade, conferir serviços/filas, owner confirmado, ativos, ticket real controlado, isolamento, erros/frescor e painel de operação. Registrar data de liberação e bloqueios específicos.
- [ ] Encerrar a expansão somente com toda identidade existente mapeada ou exceção formal e todos os tenants elegíveis ativados. Contagem inicial de cinco ativos não satisfaz cobertura produtiva.
- [ ] Conferir release, backup, fila, erros e responsáveis. Ricardo aprova/rejeita G4; risco conhecido tem owner/prazo e não substitui requisito obrigatório.
- [ ] Observar D+1/D+3/D+7 reais. Observações de releases distintas podem coexistir; não recomeçar relógio de produto intocado.

**Saída:** núcleo ness.OS em produção para o inventário e clientes existentes. Enquanto observa, preparar F6/F7; suas promoções cumprem gates próprios, sem reiniciar um programa de MVP.

## F6 — AIOps e orquestração assistidos

**Detalhe:** roteiro geral fase 8 e contratos de incidente existentes.

- [ ] Versionar alerta/incidente/enriquecimento/decisão/pós-incidente com tenant, source event ID, severidade, frescor, evidência e auditoria. Quarentenar identidade desconhecida.
- [ ] RCA e sugestão de runbook com aprovação humana explícita. Resposta da IA informa evidências e incerteza; erro/cota/custo não impede atendimento manual.
- [ ] Sanitizar Gemini/MISP: sem segredos, PII desnecessária ou outro tenant. Medir custo, latência, erros, duplicidade e intervenção humana.
- [ ] Integrar SuperOps/Atera/Datto por jornada e contrato idempotentes. Preservar GLPI como mestre e RocketCyber fora.
- [ ] Migrar n8n → Node-RED um fluxo por vez: comparação em paralelo sem duplicar efeitos externos; promover e preservar retorno antes de desativar origem.
- [ ] WhatsApp/Evolution/email/push somente quando autorizados especificamente, com opt-in quando aplicável, limite, auditoria e teste de destinatário.

**Saída:** assistência confiável e jornadas autorizadas, com falha visível e retorno. Nenhuma remediação privilegiada autônoma por presença de um botão ou webhook.

## F7 — Wazuh e Google Workspace

**Detalhe:** planos Wazuh de rollout/ingestão e roteiro geral fase 9. Versão fixada em plano antigo é candidata histórica; confirmar suporte/compatibilidade antes da release, sem upgrade incidental.

- [ ] Recalcular BOM com recursos existentes, rede privada, papéis, armazenamento, retenção e custo. Compra/provisionamento só após aprovação.
- [ ] Implantar TLS/RBAC/backup/recuperação/preflight e segregação antes de agentes. Persistir sinal normalizado antes da fila; payload bruto não entra no Hub/IA.
- [ ] Começar com até cinco endpoints internos para conferir integração/overhead; depois piloto Cavan 50–100 em lotes progressivos, incluindo checkpoints intermediários do plano de rollout. Não saltar para 100 sem prova inicial.
- [ ] Medir EPS/APS, CPU/RAM, fila, disco, retenção e agente; testar perda de spoke/rede, remoção de agente, tenant cruzado e recuperação.
- [ ] Observation mode: sem ticket GLPI, IA, Node-RED ou notificações automáticas inicialmente. Ativação de fluxo depois exige novo aceite de jornada.
- [ ] Google Workspace Cavan: leitura a cargo da ness.; superadmin apenas consentimento inicial, identidade delegada mínima protegida. Sem senha de superadmin enviada ao chat e sem Alert Center inicial.
- [ ] Normalizar auditoria Workspace com tenant/frescor/idempotência; escopos aprovados, token revogado e falha da fonte testados.
- [ ] Expandir 100 → 500 → 1.000 → 5.000 somente com gate da faixa anterior, capacidade/custo atualizados e retorno disponível.

**Saída G5:** fontes de segurança produtivas, isoladas, medidas e recuperáveis na capacidade aprovada, com todos os endpoints elegíveis do manifesto tratados ou com exceção formal. Cada faixa é entrega própria; aumentar até 5.000 exige demanda real e aprovação de capacidade.

## F8 — experiência completa e sustentação

**Detalhe obrigatório:** [matriz transversal de customização](2026-10-12-ness-branding-cross-product-plan.md); tarefas de experiência dos planos de produto.

- [ ] Completar marca nas superfícies aplicáveis: Authentik, Zabbix, GLPI, Hub/PWA, Psono, Grafana, consoles e Wazuh. Recursos pagos/ausentes têm limitação explícita; não remover atribuição obrigatória ou editar core.
- [ ] Entregar visões NOC/SOC, service desk, sustentação, governança, executivo e cliente, com fonte/fórmula/timestamp/drill-down e dados autorizados.
- [ ] Padronizar títulos únicos, pt-BR, densidade desktop, mobile, erro/vazio, contraste, foco e reduced-motion. Reusar assets aprovados, Montserrat 500 e ponto #00ade8.
- [ ] Publicar runbook por serviço: owner/substituto, dependências, SLO, alertas, backup/RPO/RTO, retorno e escalonamento; vincular GLPI. Outra pessoa exercita procedimento.
- [ ] Consolidar retenção, capacidade, custos e credenciais na revisão trimestral; reavaliar segunda cópia externa sem transformá-la em compra automática.
- [ ] Fechar fases pelo aceite, revogar manutenção temporária, preservar evidências e publicar release final/pendências aprovadas. Encerrar automação de implementação; monitoração futura tem objetivo próprio.

**Saída:** operação completa com experiência consistente, ownership e manutenção previsível. “Instalado”, “funciona localmente” e “planejado” continuam estados diferentes de entregue.

## 5. Dependências humanas que não podem ser fabricadas

| Dependência | Efeito real | Trabalho que continua |
|---|---|---|
| MFA e recuperação nominal | Bloqueia aprovação administrativa G2 | Fluxos candidatos, testes isolados, UI e outras jornadas |
| Proxy local / UUID vSphere | Bloqueia correções desses grupos e meta afetada | Demais causas de coleta, GLPI/Hub em preparação |
| SLA contratual | Bloqueia compromisso de prazo ao cliente | Catálogo, fila, atribuição e atendimento interno |
| Custo/provisionamento | Bloqueia nova VPS/cofre dedicado e expansão Wazuh | BOM, contratos de ingestão e testes locais |
| GO/corte | Bloqueia mudança de produção dependente | Deltas, pacote de release, rollback e documentação |
| Asset/licença de marca | Bloqueia superfície específica | Demais personalizações suportadas |

Registrar apenas dependência nova ou modificada; issues 51, 59, 66, 73, 74 e 75 já têm contexto. Conferir estado antes de criar duplicata. Segurança não é dispensada por indisponibilidade humana.

## 6. Livro de entregas e gates

Reusar `docs/execution/gates/ness-os-gate-register.md` e registros de execução. Se faltar arquivo, criar na execução; nenhum gerenciador novo é necessário.

Cada linha registra: fase/tarefa, ambiente, owner, estado, commit/release, evidência/data, próxima ação, bloqueio e retorno. Registrar G0/G1/G2, Z-M1–Z-M5, G3/G4/G5 e observações por promoção. Subrequisito PASS não transforma gate inteiro em PASS.

Uma entrega termina com: alteração pequena revisável, teste/readback pertinente, evidência sanitizada, commit/push e contexto atualizado. Uma fase termina com os critérios de saída acima. Uma liberação produtiva termina com smoke aprovado; encerramento operacional inclui observação aplicável.

## 7. Índice dos planos que compõem este master

| Tema | Fonte detalhada |
|---|---|
| Authentik | [Plano enxuto](2026-10-12-authentik-fluid-delivery.md) e guia operacional existente |
| Zabbix | [Plano enxuto](2026-10-12-zabbix-fluid-delivery.md); plano completo anterior e ledger para evidências |
| GLPI | [Plano completo T01–T14](2026-10-12-glpi-ness-os-complete-delivery.md) |
| Marca de todos os produtos | [Matriz transversal](2026-10-12-ness-branding-cross-product-plan.md) |
| Release/DR | [Fase 0](2026-09-18-phase-0-recovery-release-baseline.md), [release Hub](2026-10-12-hub-immutable-release-contract.md), [recuperação Hub](2026-10-12-g1-hub-recovery-evidence.md) |
| Backend tenant/sessão | [Fase 1](2026-09-18-phase-1-identity-tenant-controls.md) |
| Hub/runtime | [Fase 3](2026-09-18-phase-3-hub-runtime-reliability.md) |
| Hub/PWA/dados | [Fase 4](2026-09-18-phase-4-dashboard-operational-truth.md) |
| UAT/produção | [Fase 6](2026-09-18-phase-6-integrated-acceptance.md), [testes históricos do canário](2026-09-27-ness-os-mvp-delivery.md) |
| Wazuh | [Rollout](2026-09-18-wazuh-4147-production-rollout.md), [ingestão](2026-09-18-wazuh-security-signal-ingestion.md) |
| Psono/segredos/AIOps/Workspace | [Roteiro geral](2026-10-11-ness-os-complete-implementation-route.md), seções correspondentes, ajustadas pelas decisões deste master |

Não executar instrução histórica conflitante: segunda cópia não é requisito inicial novo; Psono dedicado não volta a decisão em aberto; versão/onda Wazuh é conferida na execução; SQL de personalização legado está substituído. Detalhes técnicos não disponíveis no plano de domínio são definidos como tarefa pequena antes da mudança, com arquivo/interface/teste exatos, sem iniciar implementação ambígua.

### Aceite global de produção

O programa só termina com núcleo produtivo cobrindo todas as entidades/ativos existentes, identidades e cofre permanentes, AIOps/jornadas aprovadas entregues, segurança na capacidade contratada, marca/runbooks e observações concluídas. Bloqueio humano/custo pode permitir liberar componentes independentes; o componente bloqueado continua pendente no programa, sem ser declarado entregue.

## 8. Próxima retomada e prazo

1. Ler este master, o topo do estágio e o final do registro da ferramenta foco.
2. Confirmar modelo executor, ordem humana de execução, janela e credenciais vigentes.
3. Fazer F0 somente para pendências; preparar F1 necessário ao acesso e retomar F2 pelo último delta. Concluir a ferramenta foco antes de abrir outra frente ampla.
4. Se houver bloqueio indispensável, registrá-lo e escolher a próxima entrega independente da mesma fase/produto; passar a outro produto apenas com resultado explícito e motivo.
5. Atualizar estimativa após cada bloco pela fila real de pendências. Não prometer implantação total em quatro horas. Liberação do núcleo e expansão são entregas distintas; observação de sete dias usa calendário real.

O plano master, os planos detalhados e as evidências estão no repositório `/home/resper/ness.OS`, remoto `resper1965/n-infraops`. Esta compilação não executou deploy, configuração, compra, envio de email ou nova auditoria de produção.
