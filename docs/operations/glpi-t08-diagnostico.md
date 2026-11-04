# GLPI T08 — diagnóstico de atendimento, catálogo e ciclo de vida

Data: 04/11/2026. Fonte: leitura (`SELECT`) no GLPI de produção (Community 11.0.x) e no código do Hub. **Nada foi escrito em produção.** Só agregados: sem nome, conteúdo de ticket, cliente ou segredo.
Escopo: seção T08 de [`2026-10-12-glpi-ness-os-complete-delivery.md`](../superpowers/plans/2026-10-12-glpi-ness-os-complete-delivery.md), a [política SOC](../specs/soc-attendance-policy.md) e a [política de recovery](zabbix-recovery-policy.md).

## 1. Conclusão

O catálogo e o roteamento por grupo existem no papel, mas **não têm efeito**: das ~105,8 mil tickets (12 entidades), **0 têm grupo ou técnico atribuído, 0 têm SLA/OLA e 0 têm prazo**. Todas nasceram com urgência 3, impacto 3 e prioridade 3. Quase todas ficam em "Novo" e na categoria genérica de infraestrutura. O Hub cria um ticket por incidente de forma idempotente, mas não envia severidade, serviço nem grupo ao GLPI.

Causa provável das regras inertes (a confirmar na homologação, por leitura de log de regra ou ticket sintético):

1. As regras 142–147 (`RuleTicket`) estão ativas com `condition = 0`. O GLPI filtra por máscara (`ONADD = 1`, `ONUPDATE = 2`), então regra com 0 não roda na criação. As regras nativas (78/79) usam `condition = 1`.
2. Os critérios usam "não é" (1) e "termina com" (5) combinados em OU. Isso casaria quase tudo, ou quase nada. Os padrões também apontam para IDs de categoria (1, 3, 6, 7, 8) que não são as categorias realmente usadas.
3. Critério de SLA com "prioridade não é N" também casaria quase tudo.

## 2. Estado atual (agregado)

| Área | Estado | Observação |
|---|---|---|
| SLAs | 8 registros (Bronze/Silver/Gold/Platinum × atendimento/resolução), `slms_id = 0`, `definition_time` nulo, calendário Default fixo | Sem SLM (tabela de SLM vazia): são órfãos. Sem unidade de tempo, o prazo é indefinido. Valores incoerentes: resolução Gold = 24 > Bronze = 5; Platinum atendimento = 15. Não vêm de contrato. |
| Níveis de SLA/OLA (escalonamento) | 0 níveis; 0 OLA | Sem alerta nem escalonamento. |
| Calendário | 1 ("Default", seg–sex 08:00–20:00), 0 feriados | Sem plantão 24x7, sem feriado, sem fuso verificado. Nenhuma entidade define calendário próprio. |
| Categorias ITIL | 29: árvore "TI" de setembro, com subcategorias de incidente, requisição, problema e mudança e grupo padrão em 22 delas | Em uso: duas folhas/nós (infraestrutura genérica ≈ 99,9%; SOC ≈ 0,1%). 1 ticket sem categoria. Nenhuma categoria tem template. |
| Templates de ticket | 1 ("Default"), só com o campo 21 (descrição) obrigatório | Nada de serviço, entidade, impacto, urgência, ativo nem motivo obrigatório. |
| Catálogo de serviços | Só no manifesto (`ness-os-foundation-v1.yaml`: 7 serviços `NESS-*`, projeto `NESS-OS-20260908`); não é campo do ticket | Não há ligação serviço→categoria→grupo→SLA no GLPI. |
| Regras de negócio | 8 `RuleTicket`: 2 nativas inativas, 6 da NESS ativas (2 de roteamento, 4 de SLA) | Ver causas acima. Efeito observado: nenhum. |
| Matriz de prioridade | Padrão do GLPI (diagonal urgência = impacto → prioridade 1–5; nível 6 sem uso) | Serve; falta o Hub informar urgência/impacto. |
| Ciclo de vida | Novo 105.824; Solucionado 1; zero em andamento, pendente ou fechado | Zero motivos de pendência, zero tipos/modelos de solução, zero validações, zero tarefas. Fechamento automático herdado da raiz; não revisado. |
| Grupos | Raiz: ALUPAR, ness, secops, infraops, devarch, trustness, forense; um "infraops/NOC" por entidade (12) | Todos aceitam atribuição. Só o grupo ALUPAR tem membro (1 usuário); `infraops`, `secops` e os 12 grupos por entidade estão vazios. |
| Perfis | Self-Service, Observer, Technician, Supervisor, Admin, Super-Admin, Operador NOC, Analista Help Desk, integração Hub, manutenção | Os perfis da matriz T08 (`ness-role-matrix.json`) ainda não existem. NOC e Help Desk sem usuários. |
| Origem da requisição | 6 padrão do GLPI; padrão "Helpdesk" | O Hub não fixa a origem. |
| Notificações de ticket | 27, 24 ativas | Canais externos devem seguir desligados (T10); não revisado aqui. |
| Volume | 2026-09: 48 mil; 2026-10: 50,6 mil; 2026-11: 7 mil (até hoje) | Backlog tratado em T09. |

## 3. Como o ticket único por incidente nasce hoje (Hub → GLPI)

`app/backend/app/workers/alerts.py`:

1. Alerta (Zabbix/Wazuh) → cliente resolvido por hostgroup (`[Cliente]`) → entidade GLPI. Cliente ambíguo é recusado.
2. Fingerprint → marcador `[n.infraops:<fingerprint>]` no título.
3. `change_active_entity`, busca pelo marcador na entidade; se existir, reutiliza.
4. Se não existir: reserva única `(entidade, fingerprint)` no Postgres **antes** do POST (advisory lock). Só quem ganhou a reserva cria o ticket; a perdedora só consulta. O POST de `Ticket` e o comentário privado "gerado automaticamente" ocorrem uma vez.
5. Campos enviados: título, conteúdo, entidade, `status=1`, **`urgency=3` fixo**, categoria (`resolve_glpi_category_id`), solicitante (usuário da integração) e, se houver, o ativo (`Computer`/`NetworkEquipment`) da mesma entidade. Nada de impacto, tipo, serviço, grupo ou origem.
6. Categoria: `NINF_GLPI_SECURITY_CATEGORY_ID` (alerta de segurança) ou `NINF_GLPI_INFRA_CATEGORY_ID`. No `.env.example` ambos são 0; em produção a evidência é a categoria 4 (genérica) e a 24 (SOC).
7. Recovery (política Zabbix): só acrescenta `ninf_zabbix_status=resolved` ao incidente local; não cria nem fecha ticket. A solução humana no GLPI volta ao Hub por `workers/resolution.py` (importa a solução, reconhece no Zabbix uma vez). Está de acordo com o T08.
8. Falhas de entrega são classificadas em [`glpi-backlog-remediation.md`](glpi-backlog-remediation.md) (T09).

## 4. Comparação com o que o T08 exige

| Exigência T08 | Estado | Lacuna |
|---|---|---|
| Comparar catálogo/categorias/grupos/projeto/runbooks com o manifesto | Parcial: 5 runbooks e 8 tarefas no JSON; 29 categorias no GLPI; serviços `NESS-*` só no YAML | Falta conferência por chave estável e ligação serviço→categoria. |
| Jornadas e transições por perfil | Inexistente | Falta `ness-role-matrix.json` e `glpi-service-operation.md`. |
| Formulários de incidente/requisição (serviço, entidade, impacto, urgência, ativo) | Só descrição obrigatória | Falta template por tipo e categoria; "desconhecido" explícito. |
| Matriz de prioridade reproduzível | Padrão do GLPI, não documentada; Hub fixa urgência 3 | Falta mapeamento severidade→urgência/impacto (seção 6). |
| Roteamento por serviço/entidade, sem pessoa padrão, fila de triagem | Regras inertes; grupos por entidade vazios; sem grupo de triagem | Falta corrigir regras, grupo de triagem e membros validados. |
| Recovery só acrescenta evidência | Implementado no Hub | Nenhuma. Falta teste sintético ponta a ponta (política Zabbix). |
| Solução automática só em caso sintético/aprovado | Não há fechamento automático pelo Hub | Revisar `autoclose_delay` herdado no GLPI. |
| SLA/TTO/TTR, calendário, feriado, fuso, pausa, escalonamento | Registros órfãos sem unidade, sem SLM, sem níveis, sem feriado | Depende de contrato (seção 6). Hoje não há prazo falso porque nada o aplica; aplicar valores sem contrato criaria prazo falso. |
| Homologação com perfis distintos, entidade permitida/negada, anexo, artigo, busca global | Não iniciada | Depende de T03 (isolamento) e dos perfis. |

## 5. Proposta de configuração mínima

Princípio: reaproveitar GLPI nativo, nada de plugin nem tabela nova; tudo por UI/API de configuração, versionado em `config/glpi/`.

1. **Triagem:** criar o grupo raiz `triagem` (atribuível, recursivo) e usá-lo como destino das regras quando não houver grupo validado para serviço/entidade. Sem pessoa por padrão.
2. **Categorias:** manter a árvore; adicionar só o necessário para os fluxos automáticos: categoria folha para alerta de infraestrutura (Zabbix) e para SOC (Wazuh), com grupo padrão (`infraops`, `secops`), e apontar `NINF_GLPI_INFRA_CATEGORY_ID` / `NINF_GLPI_SECURITY_CATEGORY_ID` para elas. Marcar o serviço pelo nome da categoria (7 serviços `NESS-*` ↔ nível 2 da árvore); não criar objeto de catálogo novo.
3. **Templates (2):** incidente (obrigatórios: categoria, urgência, impacto, ativo "se aplicável"; predefinido: origem, tipo=incidente) e requisição (categoria, descrição). Ligar por `tickettemplates_id_incident` / `_demand` nas categorias-folha.
4. **Regras `RuleTicket` (recriar, não remendar):** `condition = 1` (ao criar); critério "categoria **é** X" por folha → `_groups_id_assign`; na entidade sem grupo `infraops/NOC` com membros → `triagem`. Prioridade vem da matriz, não de regra. Regras de SLA só depois do contrato (seção 6).
5. **Hub (código, fora do GLPI):** enviar `urgency` e `impact` conforme a severidade (tabela da seção 6) e fixar `requesttypes_id`; manter urgência 3 só quando a severidade vier ausente (política SOC regra 7). Mudança pequena em `create_ticket` / `_create_glpi_ticket`.
6. **Ciclo de vida:** cadastrar motivos de pendência (aguardando cliente, fornecedor, janela, mudança), 2–3 tipos de solução e um modelo de solução; usar o fluxo nativo Novo → Em atendimento → Pendente → Solucionado → Fechado. Pendência pausa o SLA nativamente (quando houver SLA). Reabertura pelo fluxo nativo; fechamento automático só após decisão.
7. **Calendários:** manter "Default" para horário comercial; criar "24x7" e carregar feriados nacionais/estaduais depois de definir o fuso e a regra de plantão.
8. **Perfis:** criar/ajustar os perfis da matriz T08 (solicitante, técnico, NOC/SOC, gestor, administrador) a partir dos existentes; direitos de transição por perfil; testar com entidade permitida e negada.
9. **Evidência executável:** ticket sintético por severidade em entidade de teste; verificar grupo, urgência/impacto/prioridade, categoria e prazo.

## 6. SLA por severidade — PROPOSTA

**Proposta, depende do contrato e do Ricardo.** Nada abaixo foi decidido nem deve ser configurado, comunicado a cliente ou usado em relatório antes da aprovação. A tabela só dá um ponto de partida alinhado à [política SOC](../specs/soc-attendance-policy.md) (nível ≥ 12 sempre atende; 7–11 pelo score; ≤ 6 arquiva, salvo score ≥ 75).

Mapeamento proposto (severidade Zabbix / nível Wazuh → urgência = impacto → prioridade GLPI na matriz atual):

| Severidade | Zabbix | Wazuh | Urgência = impacto | Prioridade | TTO (resposta) | TTR (solução) | Calendário | Status |
|---|---|---|---|---|---|---|---|---|
| Crítica | Disaster (5) | ≥ 12 ou score ≥ 75 | 5 | 5 | 15 min | 4 h | 24x7 | proposta, depende do contrato e do Ricardo |
| Alta | High (4) | 10–11 | 4 | 4 | 30 min | 8 h | 24x7 | proposta, depende do contrato e do Ricardo |
| Média | Average (3) | 7–9 | 3 | 3 | 2 h | 24 h | 08–20 seg–sex | proposta, depende do contrato e do Ricardo |
| Baixa | Warning (2) | arquivado com amostragem semanal | 2 | 2 | 8 h | 3 dias úteis | 08–20 seg–sex | proposta, depende do contrato e do Ricardo |
| Informativa | Information (1) / não classificado (0) | ≤ 6 sem exceção | 1 | 1 | sem prazo | sem prazo (sem ticket quando Wazuh) | n/a | proposta, depende do contrato e do Ricardo |

Pontos abertos para decisão (T08 e política SOC "Aberto"):

- Valores TTO/TTR por contrato e por cliente (os níveis Bronze/Silver/Gold/Platinum existentes seguem sem base contratual; reaproveitá-los ou substituí-los?).
- Se haverá plantão 24x7 para Crítica/Alta, em quais entidades e com quem.
- Feriados e fuso do calendário; regra de pausa (só "Pendente" com motivo aprovado?).
- Escalonamento: quem recebe aos 50%, 80% e 100% do prazo (níveis de SLA).
- Se TTO/TTR valem por entidade ou globalmente (SLM por cliente?).
- Regra 4 da política SOC (regras próprias de detecção) ainda sem IDs; prazo SOC por nível depende desta tabela.

## 7. O que exige escrita no GLPI e o que é só configuração nativa

Tudo abaixo é **escrita** em produção (nada foi feito); itens nativos são por interface de administração ou API oficial, sem SQL direto (guardrail do manifesto: `prohibit_direct_database_writes`).

| Ação | Tipo | Via |
|---|---|---|
| Grupo `triagem` e membros dos grupos | Escrita | UI/API (`Group`, `Group_User`) |
| Categorias-folha de alerta; grupo e template por categoria | Escrita | UI/API (`ITILCategory`) |
| Templates de incidente e requisição (obrigatórios/predefinidos) | Escrita, nativo | UI (`TicketTemplate`) |
| Recriar/desativar regras 142–147 (condition=1, critérios "é") | Escrita, nativo | UI (Regras de negócio para tickets) |
| Motivos de pendência, tipos e modelos de solução | Escrita, nativo | UI |
| Calendário 24x7, feriados | Escrita, nativo | UI |
| SLM, SLA com unidade, níveis de escalonamento, regras de SLA | Escrita, nativo, **bloqueada pela decisão do contrato** | UI (`SLM`, `SLA`, `SlaLevel`) |
| Perfis da matriz de papéis | Escrita, nativo | UI (`Profile`) |
| Auto-fechamento/reabertura por entidade | Escrita, nativo, depende de decisão | UI (configuração de entidade) |
| Ticket sintético por severidade (homologação) | Escrita, em entidade de teste | API com a conta de integração; só depois do isolamento T03 |
| Urgência/impacto/origem enviados pelo Hub | **Não é GLPI**: alteração de código do Hub | PR em `app/backend` |
| Desativar regras 142–147 antes de recriar | Escrita | UI; reversível (reativar) |

Não exige escrita agora: este diagnóstico, o desenho da matriz de perfis e do formulário, o mapeamento de severidade (arquivos em `config/glpi/`).

## 8. Próximo passo recomendado

Aprovar a tabela da seção 6 (ou substituí-la por números do contrato), depois aplicar as seções 5.1–5.4 e 5.6 em entidade de teste, validar com ticket sintético e só então ligar as regras de SLA. Isolamento T03 continua sendo pré-requisito de qualquer POST de replay ou homologação multientidade.
