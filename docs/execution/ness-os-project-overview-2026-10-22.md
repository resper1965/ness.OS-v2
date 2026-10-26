# ness.OS — resumo do projeto, andamento e planejamento

**Fotografia documental:** 22/10/2026, 09:00 BRT. **Estado global: produção completa não liberada.** Este relatório consolida o [plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md), o [indicador datado](ness-os-status.md), o [contexto canônico](../PROJECT_CONTEXT.md), o ledger operacional local e os PRs/issues do repositório privado `resper1965/ness.OS-v2`. Não é uma nova auditoria de produção. A última atualização factual do indicador é de 15/10/2026, 12:42 BRT; a consulta GitHub desta compilação confirmou PRs #64/#81 ainda abertos em *draft* e issues de bloqueio ainda abertas. O indicador datado prevalece se houver alteração posterior.

**Correção posterior da fotografia:** o indicador foi atualizado em 22/10,
10:28 BRT; os quatro checks Actions do PR #81 passaram no SHA `5051d4c`
durante janela pública temporária e o repo voltou a privado/Actions off.
A exigência de aprovação de segundo revisor na `main` foi removida por decisão
do único desenvolvedor, mantendo quatro checks strict e admin enforcement.
PR #42 e issues #67/#68/#80 foram encerrados como substituídos/organizados;
nenhum merge/deploy decorreu. O caminho de retomada vigente é o
[handoff de desenvolvimento](developer-handoff-2026-10-22.md); o restante
deste resumo preserva a fotografia original para comparação.

## Resumo executivo

O ness.OS deve operar para **todas as entidades e ativos existentes elegíveis**, não apenas para um MVP demonstrativo. A jornada central é `evento Zabbix → incidente no Hub → ticket GLPI → acompanhamento e solução`, com identidade Authentik, segredos no Psono, automação assistida em Node-RED, segurança Wazuh/Google Workspace, isolamento por tenant e experiência ness. O canário de 5–10 ativos internos inicia a expansão; não encerra o programa.

Há base técnica e partes produtivas já comprovadas: Hub/AIOps anterior promovido por imagens imutáveis com rollback ensaiado; volume persistente GLPI e guarda da API pública corrigidos; destino Zabbix restaurado em isolamento; restauração externa isolada pós-rotação concluída com código 0; código candidato de GLPI/CI testado localmente; imagens candidatas privadas de API/frontend publicadas e puxadas por digest. **Nenhuma dessas provas, isoladamente, aprova G0–G5, o corte Zabbix, T03 GLPI, o PR #64/#81 ou a produção global.**

O caminho crítico atual é: substituir os quatro checks da `main` por CI local **com signer isolado do builder**, revisar/promover o pacote por digest, provar a fronteira direta da API GLPI e só então considerar reativar a conta técnica 106, reconciliar ativos/tickets e liberar a jornada integrada. A janela de mutações Zabbix terminou em **15/10/2026 11:47:35 BRT** e o token anterior expirou; nenhuma automação renova ambos.

## Escopo, arquitetura e decisões vigentes

| Domínio | Responsabilidade e decisão |
|---|---|
| Authentik / Psono | SSO central e MFA/autorização efetiva; cofre de produção dedicado, com Ricardo e Ismael como custodians e recuperação independente. Custo/provisionamento ainda exigem aprovação. |
| Zabbix | Monitoração de todo o inventário elegível. Origem permanece a única coletora; destino isolado e mascarado até o corte autorizado. Cavan — Matriz é piloto obrigatório. |
| GLPI | Cadastro mestre de ativos e ITSM; direitos nativos, filas, catálogo e ciclo de ticket. O Hub não substitui a fronteira de autorização GLPI. |
| Hub / PWA | Integra dados e jornadas por tenant/papel; backend impõe escopo e informa origem, frescor, erro e qualidade. |
| AIOps / Node-RED | RCA e runbooks assistidos, com aprovação humana para ações privilegiadas; atendimento manual sempre disponível. |
| Wazuh / Workspace | Segurança produtiva por faixas e leitura mínima, depois de núcleo seguro e capacidade/custo aprovados; sem Alert Center inicial. |
| Continuidade | RPO ≤24 h, RTO ≤4 h; SLO inicial portal/API 99,5% e ingestão Zabbix 99,9%. Contabo Object Storage é a única cópia externa inicial, risco aceito e revisão trimestral; isto não equivale a 3-2-1 integral. |
| Dados e canais | Alertas brutos 90 dias, incidentes qualificados 12 meses; retenção de tickets/anexos/auditoria requer política própria. Hub e GLPI são os canais iniciais; email/WhatsApp/push dependem de autorização específica. |
| Governança | Mudança produtiva exige owner, identidade, ticket, janela, backup/readback e rollback. Não inventar tenant, SLA, ativo, aceite nem GO. Novas compras/provisionamento pedem aprovação específica. |

## Andamento comprovado por fase

| Fase | Estado | Entregue ou verificado | Falta para a saída da fase |
|---|---|---|---|
| F0 — release e continuidade | Parcial | PR #65 integrado; release anterior Hub/AIOps e rollback ensaiados; histórico de heads/tags sanitizado após rotação; restore externo isolado pós-rotação `PASS` para o conjunto documentado; PR #81 executou checks/scan locais e publicou/puxou imagens privadas por digest. | CI externo confiável, revisão/integração de PRs, correspondência release-runtime, refs de PR/caches históricos com GitHub Support, gates G0/G1 por evidência. |
| F1 — identidade e cofre | Parcial | Branding público e SAML técnico Authentik; inventários e recuperação histórica do Psono. | MFA e recuperação nominais, bindings Google, jornadas por aplicação/tenant, cofre dedicado e custodians comprovados; G2 aberto. |
| F2 — Zabbix | UAT preparada; corte bloqueado | Destino restaurado/isolado; origem única coletora. Referência histórica: 262 hosts reais e 63 protótipos; dois hosts SNMP corrigidos de 994 para 2 erros. | Qualidade/frescor em toda a frota (última amostra 2,086% unsupported), proxy/Windows/UUID VMware, SSO, gates, GO, freeze e nova janela/token antes do corte; Z-M5 e observação. |
| F3 — GLPI | Em execução | Volume `/var/glpi` persistido com retorno preservado; guarda pública Caddy; paginação e identidade defensivas na branch; gateway candidato e T04 com reserva idempotente testados em isolamento; tema opt-in instalado sem seleção. | Isolamento **direto** T03, imagem/release e matriz negativa real; conta 106 inativa; três ativos não criados; migração T04 e replay não executados; agentes, RBAC, catálogo, jornadas e aceite nominal pendentes. |
| F4 — Hub/PWA | Parcial | Runtime anterior promovido e rollback ensaiado; melhorias de integração/telemetria na branch. | G3, dados e permissões reais por tenant, readiness/degradação, PWA e jornadas desktop/móvel em produção. |
| F5 — operação integrada | Pendente | Ensaios isolados de fluxo, retry e tenant, sem equivalência à jornada real produtiva. | Canário evento→incidente→ticket, replay/timeout/recovery, negação cruzada, G4 e expansão para todas as entidades elegíveis com observação D+1/D+3/D+7. |
| F6 — AIOps/automação | Parcial | Componentes existentes e alguns contratos/ensaios locais. | RCA, runbooks, custos/PII e fluxos Node-RED aprovados sobre incidentes reais, sem ação privilegiada autônoma. |
| F7 — Wazuh/Workspace | Sem aceite produtivo | Planos de rollout e ingestão; não confundir provider/módulo existente com serviço aceito. | BOM/custo, capacidade, isolamento, recuperação, pilotos e G5 por faixa; Workspace com escopos mínimos. |
| F8 — experiência/sustentação | Parcial | Marca em superfícies específicas; paleta GLPI opt-in. | Render nominal, cobertura de marca, painéis por perfil, runbooks exercitados, retenção/revisão e observações de releases. |

### Marcos relevantes e limites da evidência

1. **12/10 — base operacional:** release imutável anterior do Hub/AIOps, rollback e provas de recuperação; inventário Zabbix de referência e backlog GLPI registrados. São evidências do pacote e data correspondentes, não auditoria atual da frota.
2. **13/10 — GLPI:** migração controlada do estado `/var/glpi` para volume nomeado com 5.780 arquivos comparados; guarda pública real da API com UI/SSO preservados. A API nativa também reproduziu acesso indevido à entidade descendente por identidade não recursiva; por isso a conta **106 continua desativada**. O gateway privado, guard de entidade, paginação e reserva T04 são candidatos de branch/ensaio, não isolamento ou migração produtiva.
3. **13–14/10 — release e segredos:** PR #65 entrou na `main` por exceção administrativa pontual documentada e proteção restaurada. Após exposição em diagnóstico, credenciais S3/Restic/MariaDB pertinentes foram rotacionadas; restore externo isolado pós-rotação terminou com `exit 0` e `PASS`. Heads/tags foram sanitizados; refs de PR/caches permanecem pendentes de limpeza externa. Não repetir restore sem mudança relevante.
4. **14/10 — CI local:** Actions ficou desativado por cobrança. O PR #81 passou checks locais completos, scan sanitizado e pull por digest; uma cópia candidata do launcher/política foi instalada fora do PR. A App `ness-os-local-ci` existe apenas para o repositório, mas não emitiu checks. A primeira chave ainda aparece ativa; faltam leitura mínima de PR, readback de `head.sha`, signer separado do acesso ao Docker e falhas negativas ponta a ponta.
5. **15/10 — Zabbix:** encerramento da janela autorizado foi registrado às 12:42 BRT, após o limite de 11:47:35. Não há novo readback operacional nesse registro. Origem única coletora e destino mascarado são o último estado documentado; sem autorização nova, não há DNS, desmascaramento ou dupla coleta.
6. **22/10 — repositório:** consulta documental encontrou PRs [#64](https://github.com/resper1965/ness.OS-v2/pull/64) e [#81](https://github.com/resper1965/ness.OS-v2/pull/81) abertos em *draft*. A `main` remota ainda não contém `docs/`; esta fotografia parte do branch de entrega do PR #64. Nenhum deploy, gate ou estado de produção foi inferido dessa consulta.

## Bloqueios e decisões humanas

| Dependência | Efeito | Fonte/conduta segura |
|---|---|---|
| CI local confiável | Quatro checks obrigatórios da `main` continuam associados ao app Actions; não há emissor substituto aceito. | PR [#81](https://github.com/resper1965/ness.OS-v2/pull/81). Separar signer do domínio do Docker (ou provar isolamento equivalente), obter `Pull requests: Read-only`, confirmar `head.sha`, revisar evidência/falhas negativas e revogar a primeira chave antes de trocar a origem dos checks. Não emitir status parcial. |
| GLPI T03 / G2 | Rota direta Hub/worker→GLPI ainda existe, embora a pública esteja guardada; seleção de descendente foi reproduzida. | [ADR 0020](../adr/0020-glpi-maintenance-entity-boundary.md), [issue #74](https://github.com/resper1965/ness.OS-v2/issues/74). Conta 106 inativa; sem novos ativos, replay ou liberação cliente até matriz negativa real e rollback. |
| Zabbix | Janela/token vencidos; metas de qualidade, SSO/gates e GO ainda pendentes. | [Plano Zabbix](../superpowers/plans/2026-10-12-zabbix-fluid-delivery.md), [issue #73](https://github.com/resper1965/ness.OS-v2/issues/73). Nova autorização específica precede qualquer mutação. |
| Histórico remoto | Heads/tags limpos não removem refs de PR/caches retidos. | [Issue #82](https://github.com/resper1965/ness.OS-v2/issues/82); obter limpeza/retorno do GitHub Support, sem publicar segredos. |
| GLPI identidade, agentes e aparência | 33 pares de login ativo/ativo têm grants divergentes; sete agentes estavam sem contato desde julho; tema não foi validado em sessão nominal. | [#77](https://github.com/resper1965/ness.OS-v2/issues/77), [#79](https://github.com/resper1965/ness.OS-v2/issues/79), [#78](https://github.com/resper1965/ness.OS-v2/issues/78). Sem dedupe em massa, instalação de agente ou seleção global por suposição. |
| MFA/cofre/SLA/capacidade | Pessoas, contrato e custo não podem ser simulados. | Issues e plano master. Continuar preparação isolada; promoção dependente espera prova/decisão específica. |

## Planejamento completo de entrega

As fases abaixo são dependências e critérios, não datas prometidas. Cada alteração produtiva usa precondição, escopo, readback, owner e rollback; ondas de ativos têm até cinco unidades e abortam ante conflito de identidade/tenant. [Plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md) e planos de domínio contêm as listas executáveis completas.

| Ordem | Trabalho planejado | Condição de promoção / saída |
|---|---|---|
| F0 | Fechar release identificado por commit/Compose/digests; CI limpo e externo confiável; secret scan/SBOM; backup, retenção e recuperação aplicável. | G0/G1 por prova correspondente; nenhuma promoção apenas por teste local. |
| F1 | Corrigir bindings Google; provar MFA, recuperação, revogação e autorização nativa/Hub; promover Psono dedicado e rotacionar segredos por consumidor. | G2 por requisito, cofre recuperável e identidade permanente. |
| F2 | Reconciliar todos os hosts/protótipos; corrigir coleta por causa em ondas; atingir frescor e metas; concluir SSO/GO; freeze único, corte sem dupla coleta, smoke, painéis e D+1/D+3/D+7. | Z-M5, origem parada antes do destino coletar e retorno comprovado; nova janela necessária. |
| F3 | Executar GLPI T01–T14 na sequência de gates abaixo; isolar acesso nativo antes da escrita; reconciliar CMDB/atendimento e homologar jornada. | T03 e demais contratos aceitos; GLPI mestre efetivo, não apenas contagens reduzidas. |
| F4 | Promover Hub/PWA por digest com migrations/rollback; validar degradação, HTTP/SSE, tenant/papel, fontes/frescor, dashboards e experiência móvel. | G3 e matriz de ativação por entidade com dados reais. |
| F5 | Canário interno de evento→incidente→ticket com repetição/timeout/recovery e perfis; expandir Cavan — Matriz e demais entidades elegíveis por ondas, com observação. | G4 por liberação, cobertura total ou exceção formal; aprovação de Ricardo e D+1/D+3/D+7. |
| F6 | Versionar decisão/enriquecimento/RCA; sanitizar IA e medir custo; migrar n8n→Node-RED fluxo a fluxo sem efeito duplo; ações privilegiadas com aprovação. | Jornadas assistidas auditáveis, erro visível e atendimento manual preservado. |
| F7 | Aprovar BOM/custo; isolar Wazuh e testar backup; pilotar até cinco endpoints internos, depois Cavan 50–100 e faixas progressivas; Workspace com leitura mínima. | G5 por faixa, capacidade/recuperação/tenant comprovados; 5.000 é teto arquitetural, não frota confirmada. |
| F8 | Completar marca e painéis por perfil, acessibilidade, runbooks exercitados, retenção/custos, observação e revogação temporária. | Aceite global de produção e sustentação por owners/substitutos. |

### GLPI — plano T01–T14 e estado de cada trilha

| Tarefa | Próximo trabalho e condição |
|---|---|
| T01 ambiente/estado | Volume persistente e guarda de backup entregues; completar smoke nominal de login/perfil/ticket/anexos e evidência do ciclo agendado aplicável. |
| T02 consumidor | Guard de entidade efetiva e falha fechada no Hub candidatos; promover só com release e negativas por papel/entidade. |
| T03 manutenção | Provar separação de rede/rota direta, Caddy autenticado, entidade descendente, IDOR, search/export/batch/replay e rollback; só depois considerar conta 106. |
| T04 ticket idempotente | Reserva durável e migração aditiva candidatas; aplicar esquema antes do worker em janela autorizada, reconciliar resultado ambíguo e testar concorrência/timeout real antes de replay. |
| T05 três ativos | Após T03, criar/reconciliar 10983/10984/10987 e vínculos elegíveis em onda controlada; sem inventar owner/tenant. |
| T06 inventário | Reconciliar todo o inventário por identificador, preservando sintéticos, duplicidades de representação e identidade física incerta. |
| T07 agentes | Confirmar identidade/rota e testar POST autenticado/negação cruzada; piloto de cinco internos e expansão com frescor/remoção. |
| T08 catálogo/atendimento | Reusar serviços, grupos e runbooks; configurar solicitante/técnico/gestor, atribuição e solução. SLA só após contrato aprovado. |
| T09 backlog | Classificar incidentes/tickets e reconciliar antes de replay; 159 sem ticket foram classificados historicamente, 15 sem source ID seguem em quarentena; sem fechamento/exclusão em massa. |
| T10 experiência | Validar paleta `ness.` opt-in com login nominal, móvel/desktop/contraste e retorno antes de default. |
| T11 painéis | Entregar visões por perfil com dados reais, fonte, frescor e drill-down no GLPI/Hub. |
| T12 runtime/plugins | Investigar ações internas atrasadas e registros de plugin sem código; não forçar scheduler, apagar tabelas ou atualizar plugins em bloco. |
| T13 release/canário | Promover imagem por digest e executar smoke, isolamento e fluxo ticket com rollback; não confundir branch verde com release. |
| T14 sustentação | Documentar owner, backup, retorno, observação e aceite funcional por perfil/entidade. |

### Liberações e próxima sequência operacional

1. **P1 — núcleo produtivo:** resolver F0/CI e acesso F1 necessário; concluir F2/F3/F4 e a jornada F5 em canário. Liberar apenas depois de smoke e isolamento, então expandir para todos os elegíveis enquanto a observação corre.
2. **P2 — operação assistida:** RCA/runbooks, fluxos Node-RED autorizados, portal/PWA e visões por perfil com custo/PII/retorno comprovados.
3. **P3 — segurança:** Wazuh por faixa e Workspace leitura mínima, com capacidade, isolamento, recuperação e G5 próprios.
4. **P4 — encerramento:** cobertura completa, marca, runbooks, observações e revogação de acessos temporários; aceite global, sem chamar instalação parcial de entrega.

**Próximo bloco executável:** manter GLPI T03 como frente principal. Preparar e ensaiar isolamento efetivo Hub/worker→GLPI sem tocar a conta 106; em pré-requisito de release, separar o signer de CI do builder, obter permissão mínima/readback e provar falha fechada. Se T03 não puder avançar, escolher **uma** tarefa GLPI independente e reversível (por exemplo, classificação T12 ou validação nominal T01/T10 quando houver identidade), sem replay, dedupe ou configuração contratual presumida. Só após revisão/CI/digest/matriz negativa real promover GLPI. Zabbix exige nova janela, token, gates, freeze, GO e rollback antes de qualquer corte.

## Fontes e manutenção deste resumo

- [Indicador datado](ness-os-status.md) — autoridade para último estado factual; atualizar somente quando entrega, gate, bloqueio, foco ou prazo mudar.
- [Plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md) — objetivo, F0–F8, P1–P4 e critérios de saída.
- [Planos GLPI](../superpowers/plans/2026-10-12-glpi-ness-os-complete-delivery.md), [Zabbix](../superpowers/plans/2026-10-12-zabbix-fluid-delivery.md), [Authentik](../superpowers/plans/2026-10-12-authentik-fluid-delivery.md) e [marca](../superpowers/plans/2026-10-12-ness-branding-cross-product-plan.md) — tarefas completas de domínio.
- [Contexto canônico](../PROJECT_CONTEXT.md), [handoff](ness-os-handoff-2026-10-14.md), [ADR GLPI](../adr/0020-glpi-maintenance-entity-boundary.md) e ledger operacional local `.superpowers/sdd/2026-10-12-ness-os-plano-master/progress.md`. O ledger local não é evidência publicada por este relatório; dados produtivos exigem os registros específicos.
- O registro de gates ausente na fotografia das 09:00 foi criado depois como
  [índice de retomada](gates/ness-os-gate-register.md), sem novo PASS por
  inferência. O indicador continua a fonte do estado factual.

Este documento é uma fotografia de planejamento e andamento. Não contém credenciais, tokens, dumps ou dados pessoais operacionais; não modifica ambiente, regras da `main`, PRs de implementação nem gates.
