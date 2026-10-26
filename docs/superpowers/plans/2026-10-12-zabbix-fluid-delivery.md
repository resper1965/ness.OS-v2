# Zabbix — plano enxuto de liberação no ness.OS

> **Somente planejamento. Não implementar com o modelo autor.** Retomar após troca de modelo e instrução humana de execução. Usar `ponytail:ponytail` full e `superpowers:executing-plans`. Automação antiga permanece pausada.

**Objetivo:** concluir a migração, qualificar a coleta de todos os ativos existentes e entregar operação e painéis utilizáveis.

**Arquitetura:** origem como coletor único até o corte; destino isolado para preparar configuração. Reutilizar scripts, deltas e registro de ativos existentes. Configuração nativa antes de código novo.

**Stack:** Zabbix 7.0, API JSON-RPC, proxies/agentes/SNMP, MariaDB, Authentik/SAML, systemd e scripts Python/shell existentes.

**Referências:** `docs/execution/project-stage-2026-10-12.md`, `docs/execution/zabbix-production-window-2026-10-12.md`, `.superpowers/sdd/2026-10-12-zabbix-complete-delivery/progress.md` e plano anterior `2026-10-12-zabbix-complete-delivery.md`. Este plano substitui a ordem de execução anterior; mantém seus critérios de segurança e aceite. O ledger e o estágio mais recente prevalecem sobre caixas antigas ainda desmarcadas.

## Ponto de partida

Evidências registradas, não nova auditoria de produção:

| Já comprovado — preservar | Ainda necessário |
|---|---|
| Restore f0b19cf8, paridade, banco/API/frontend e durabilidade | Sincronização final no corte, pois a origem continuou recebendo dados |
| 262 hosts reais, 261 ativos e 10877 desativado; 63 protótipos | Resultado por ativo, incluindo sem coleta e exceções |
| SNMP 10768/10769: 994 erros → 2, três ciclos reais, IDs preservados | Windows/proxy, VMware, cálculos e demais causas da frota |
| Recuperação UAT e SAML técnico | Login nominal, MFA, revogação/logout e acesso técnico mínimo |
| Painéis 406/407, branding e ensaios UAT | Publicação no destino definitivo, perfis, dados atuais e acabamento |
| Origem segue coletando; destino mascarado | GO, corte sem dupla coleta e acompanhamento |

Última amostra global: **749 itens não suportados / 35.905 habilitados = 2,086%**. Meta existente: **<0,5% global** e redução **≥70% no escopo FortiGate relevante**. A melhora de dois hosts não aprova a frota inteira.

## Regras Ponytail para execução fluida

- Reusar o que existe. Sem nova arquitetura, novo framework, script genérico ou refatoração paralela.
- Um diagnóstico por causa; uma correção pequena; um teste relevante; readback; seguir adiante.
- Ondas de até cinco hosts. Não reabrir onda aprovada sem regressão ou mudança que a afete.
- Não repetir dump, importação, restore, branding ou ensaio aprovado para “retomar contexto”. Consultar a evidência existente.
- Backup final de migração é necessário; novo teste de restore sem mudança relevante não é.
- Falta de acesso a um proxy bloqueia aquele diagnóstico, não as demais tarefas independentes.
- Atualizar o ledger existente; um commit por entrega coerente, não por consulta. Mostrar progresso em até 60 segundos durante execução ativa.
- Nunca economizar em isolamento, preservação de dados, autorização ou rollback.

## Limites preservados

- Origem `144.91.72.202` é a única coletora; destino `169.58.234.9` permanece isolado até corte aprovado.
- Não ativar 10877, limpar templates com histórico, inventar UUID/tenant/owner ou trocar erro por valor saudável.
- Não elevar conta Hub, escrever configuração por SQL, expor credencial ou liberar ações/mídias em massa.
- Janela antiga: até **13/10/2026 11:47:35 BRT**. Conferir janela e credenciais na retomada; após expiração, obter nova janela antes de mutações produtivas.
- G0/G1/G2 e gates de migração continuam exigidos. Issue aberta não é PASS. GO formal e mudança aprovada continuam necessários.
- RPO ≤24h e RTO ≤4h. Exceção aparece no relatório e não sai do denominador para melhorar métrica. Alterar critério de aceite exige decisão expressa, não conveniência do executor.

## 1. Retomar pelo delta — uma única passagem

**Usar:** estágio, ledger e `config/zabbix/asset-register-20261012.json`.

- [ ] Ler o último resultado e conferir Git, janela, validade de acesso e alterações posteriores. Não relançar jobs concluídos.
- [ ] Atualizar somente ativos/configurações alterados e confirmar papéis origem/destino. Registrar novidade que invalide evidência anterior.
- [ ] Separar lista de trabalho em: correção autônoma, acesso humano indispensável e acabamento pós-corte.

**Pronto quando:** existe uma lista curta de pendências por causa e os 262 hosts/63 protótipos continuam contabilizados, ou suas alterações estão explicadas. Sem percentual subjetivo de progresso.

## 2. Fechar coleta por causa e aplicar em ondas

**Usar:** `infra/scripts/zabbix-quality-wave.py`, `zabbix-asset-register.py`, `zabbix-freshness.py`, `zabbix-snmp-variant.py` e testes correspondentes em `infra/tests/`. Deltas em `config/zabbix/`.

| Frente | Próxima ação concreta | Evidência suficiente |
|---|---|---|
| Windows/proxy 1 | Obter diagnóstico local da issue 73; conferir chegada de configuração e execução antes de mudar contador/template | Contadores candidatos realmente executados pelo proxy correto; três amostras novas válidas |
| VMware: 10787/88/89/90/92/93 | Obter UUIDs na fonte vSphere autoritativa e conferir correspondência | Macro correta, descoberta e itens essenciais atualizados |
| Cálculos de disco | Confirmar capacidade e aplicabilidade de 85776/85997 | Cálculo válido ou limitação do modelo documentada; sem esconder erro |
| Hosts sem itens/template | Classificar os 14 sinalizados e atribuir template somente com tecnologia/função comprovadas | Coleta real ou exceção formal; tag unconfigured não basta |
| Demais ativos | Agrupar erros por causa: chave/OID, credencial, conectividade, intervalo ou descoberta | Correção mensurada por onda e estado por host |
| Cavan appliance/links | Reusar variante 10989 e ensaio de IDs; provar dois ciclos LLD antes de restringir interfaces | Interfaces previstas, histórico preservado e retorno comprovado |

- [ ] Preservar probes Windows encerrados; só fazer novo ensaio limitado após diagnóstico novo justificar. Não repetir TCP da origem para agente atrás de proxy.
- [ ] Por onda: export antes → verificar precondição → aplicar API normal → ler resultado → observar ciclos necessários. Se falhar, compensar somente o delta da onda.
- [ ] Para lógica nova, escrever um teste pequeno que reproduza o problema e provar correção. Para ajuste nativo simples, API readback e coleta real bastam; não rodar suites de produtos não alterados.
- [ ] Conferir IDs/histórico preservados, novos itens LLD legítimos e ausência de regressão. Não alterar template compartilhado para resolver incompatibilidade isolada.
- [ ] Atualizar registro de todos os hosts e protótipos com resultado, evidência, lacuna e responsável. Freshness de ping não prova saúde de todos os serviços.

**Pronto quando:** cobertura completa do inventário, métricas essenciais recentes e metas de qualidade aprovadas. Pendência crítica não vira aceite por estar numa issue. Se limitação externa impedir a meta, apresentar o impacto e a decisão necessária; continuar causas independentes.

## 3. Concluir acesso e liberar os gates

**Usar:** scripts SAML/readiness existentes e issues 51/73 e demais gates já registrados.

- [ ] Homologar uma conta nominal por papel necessário: login, MFA, logout, usuário revogado e acesso negado fora do tenant. Recuperação administrativa UAT já aprovada não precisa ser refeita.
- [ ] Confirmar identidade técnica permanente mínima e rota autorizada; token temporário administrativo não prova menor privilégio.
- [ ] Reutilizar evidências válidas de release, backup e recuperação. Renovar apenas requisito vencido ou afetado; idade do backup se verifica no manifesto.
- [ ] Consolidar checklist PASS/FAIL/BLOCKED, mudança, janela, owner, retorno e GO de Ricardo. Não reenviar cobranças humanas já enviadas sem novidade.

**Pronto quando:** acesso real e gates obrigatórios aprovados. Tarefas 2 e 3 podem avançar independentemente; nenhuma depende de acabamento visual.

## 4. Fazer um único corte definitivo

**Usar, após ler efeitos:** `zabbix-final-freeze-backup.sh`, `zabbix-refresh-isolated-destination.sh`, `zabbix-cutover-enable-production.sh`, `cloudflare-zabbix-dns-cutover.sh`, `zabbix-post-cutover-reconcile.sh`, `monitor-zabbix-proxy-reconnect.sh`.

- [ ] Consolidar deltas UAT que sobreviverão ao refresh: identidade/SAML, painéis, branding e configurações aprovadas. Replay aceita somente estado anterior esperado ou estado final idêntico; conflito aborta.
- [ ] Registrar TTL, endpoints de proxies/agentes, buffers disponíveis, responsáveis e sequência de retorno. DNS sozinho não move clientes com IP fixo.
- [ ] Congelar configuração e interromper a coleta da origem conforme runbook; gerar snapshot final consistente. Registrar início da interrupção e limite de retorno aprovado para a janela.
- [ ] Restaurar o snapshot final no destino isolado, aplicar apenas deltas ainda necessários e verificar configuração, SSO e ausência de canais externos.
- [ ] Mover endpoints/DNS autorizados e iniciar somente a coleta do destino. Confirmar origem parada, proxies reconectados e dados novos; nenhuma dupla coleta.
- [ ] Smoke: UI/API/SSO, itens essenciais de cada grupo/proxy, fila, NVPS, busy, incidente/recovery controlado e integração Hub. Comparar com baseline e limites registrados antes do corte.
- [ ] Abortar se houver dupla coleta, falha de acesso essencial, perda de integridade ou ausência de dados novos após três intervalos dos itens sentinela. Parar destino antes de devolver coleta à origem; reconciliar dados exclusivos do destino antes de descartá-los.

**Pronto quando:** destino é a única produção, dados chegam, acesso e integração passam e retorno continua disponível. Canais externos permanecem conforme escopo Hub/GLPI; não ativar mídias reais por efeito colateral.

## 5. Entregar painéis, mapas e marca sobre dados reais

**Cobertura ampliada:** seguir a linha Zabbix da [matriz transversal ness.](2026-10-12-ness-branding-cross-product-plan.md), incluindo navegação, relatórios e mobile, além de logo/painéis. Preservar severidades, licença e funcionalidades técnicas.

**Usar:** dashboards existentes em `config/zabbix/`, módulo `infra/zabbix/modules/ness_mobile/` e verificadores de navegador existentes. Não recriar painéis 405/406/407 ou reinstalar branding aprovado.

- [ ] Reaplicar/promover somente deltas necessários; preservar originais. Remover rótulo UAT/snapshot apenas após fonte produtiva realmente ativa.
- [ ] Entregar quatro visões: operação NOC, qualidade da coleta, capacidade do Zabbix e cliente. Exibir escopo, atualização, denominador e dados indisponíveis.
- [ ] Mapas mostram relações confirmadas; localidade/criticidade vêm do cadastro aprovado. Sem topologia inventada por semelhança de nomes.
- [ ] Validar acesso por perfil, desktop e móvel, navegação, widgets, pt-BR, contraste e títulos únicos. Marca ness. segue a skill de branding, em camada reversível.

**Pronto quando:** os usuários conseguem investigar problemas reais e cada cliente vê apenas seu escopo. Rollback visual desativa a camada/delta; não exige restaurar banco.

## 6. Observar e encerrar

- [ ] Atualizar runbook existente com operação, falha de proxy, filas, backup, retorno, owner e substituto; executar um procedimento com outra pessoa quando disponível.
- [ ] Observar D+1/D+3/D+7 a partir do corte real: coleta, erros, incidentes, capacidade, backup e regressões. Isso não impede uso produtivo após o smoke aprovado.
- [ ] Preservar origem 7–14 dias. Sua desativação definitiva é ação controlada posterior, sem exclusão antecipada.
- [ ] Revogar acessos temporários, fechar sessões e publicar evidências sanitizadas, commit e pendências residuais aprovadas.

**Pronto quando:** operação estável, todos os ativos tratados ou com exceção formal compatível com o aceite, painéis aceitos e observação concluída. Separar “liberado em produção” de “capítulo encerrado”.

## Revisão mínima antes de promover

Cinco casos obrigatórios: host desativado permanece assim; alteração fora de precondição aborta; LLD preserva histórico; replay do delta não duplica configuração; dado atrasado não aparece saudável. Rodar testes apenas dos componentes alterados e os smoke tests afetados. Ampliar testes quando surgir regressão, não por rotina.

## Ritmo e previsão honesta

Primeiro bloco: retomada curta, diagnóstico Windows/VMware e fechamento de acesso. Segundo: ondas de coleta e gates. Terceiro: corte, seguido de acabamento e observação. Aguardar três ciclos é parte da prova; aguardar humano em um item não suspende o restante.

Após o primeiro bloco, estimar o corte usando pendências reais e volume/duração do snapshot já medidos. Não prometer horário antes de conhecer acesso ao proxy, UUIDs e homologação SSO. O encerramento inclui sete dias de observação; a liberação produtiva pode ocorrer antes.

**Handoff:** ler este plano, último estágio e ledger; confirmar troca de modelo, ordem de execução e janela vigente; seguir a etapa 1. Este plano não iniciou jobs, alterou produção ou reativou automação.
