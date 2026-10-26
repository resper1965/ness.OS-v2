# Especificação inicial — Projetos de TI no ness.OS

> Estado: requisito confirmado; GLPI Community é a direção provisória e depende de validação/piloto.
> Princípio: GLPI registra e governa; ness.OS consolida, explica e apresenta.

## Baseline observada em 21/08/2026

Inspeção somente leitura na VPS AIOps confirmou:

- GLPI CLI **11.0.8**;
- classes nativas `Project` e `ProjectTask` presentes na instalação;
- contêiner `ninf-glpi` ativo, com a aplicação exposta apenas na porta interna `80/tcp`;
- imagem `elestio/glpi:latest` fixada pelo digest `sha256:48ec3ce559d...` em 21/08/2026;
- MariaDB do GLPI em contêiner separado, versão `10.11`.

A imagem e o caminho de rollback já foram fixados. O inventário posterior confirmou zero projetos e zero tarefas, permitindo iniciar o piloto sem confundir registros anteriores. A carga está descrita no manifesto versionado [`../../config/glpi/ness-os-foundation-v1.yaml`](../../config/glpi/ness-os-foundation-v1.yaml) e depende de autenticação API de menor privilégio; escrita direta no banco é proibida.

## Objetivo

Controlar e acompanhar projetos de TI de stakeholders, clientes e áreas internas, relacionando execução, serviços, ativos, chamados, mudanças, riscos, custos e resultados. O módulo deve responder rapidamente:

- o que está em andamento, para quem e por quê;
- quem patrocina, gerencia e executa;
- o que está no prazo, em risco, atrasado ou bloqueado;
- qual é o próximo marco e qual decisão é necessária;
- quais serviços, clientes, ativos, mudanças e incidentes são afetados;
- qual benefício foi prometido e se foi realizado.

## Fronteira do produto

O GLPI será avaliado como fonte canônica do portfólio e do acompanhamento gerencial. Ferramentas técnicas como GitHub/GitLab ou outra plataforma de execução poderão continuar cuidando de issues, sprints e código, ligadas ao projeto por URL ou adaptador. O ness.OS não deve replicar cada tarefa técnica nem se transformar em outro gerenciador genérico de tickets.

## Capacidade disponível no GLPI Community

A documentação oficial descreve projetos e subprojetos hierárquicos, tarefas/subtarefas, equipes, datas planejadas e reais, percentual, Gantt, Kanban, custos e vínculos com objetos ITIL. Projetos também podem se relacionar com tickets, mudanças, problemas, contratos, documentos, conhecimento e itens do inventário.

Isso cobre o MVP sem nova aplicação ou VPS. A adequação real depende da versão instalada, dos perfis, da separação por entidade/tenant, dos campos necessários e da API disponível.

## Cadastro mínimo obrigatório

| Grupo | Campos mínimos |
|---|---|
| Identidade | código, nome, descrição curta, tenant/entidade, tipo e prioridade |
| Governança | sponsor, gerente, equipe, área demandante e aprovador |
| Alinhamento | serviço GLPI relacionado, objetivo, benefício esperado e critério de sucesso |
| Planejamento | início/fim planejados, próximo marco, dependências e orçamento aprovado quando aplicável |
| Execução | estado, percentual, início/fim reais, custos, bloqueios e última atualização |
| Saúde | verde/amarelo/vermelho, justificativa, decisão necessária e data de revisão |
| Relações | tarefas, subprojetos, tickets, problemas, mudanças, contratos, ativos e links técnicos |
| Encerramento | aceite, resultado, benefício observado, lições aprendidas e documentos finais |

Se algum campo não existir nativamente, a primeira preferência será dropdown/campo adicional suportado e versionável; customização de núcleo é proibida.

## Fluxo de estados inicial

`proposto → em análise → aprovado → planejado → em execução → em espera → concluído → cancelado`

“Em risco” e “atrasado” são estados de saúde, não substitutos do estágio do projeto. Um projeto em execução pode estar amarelo ou vermelho. Toda saúde manual precisa de justificativa e validade; depois da validade, torna-se `stale`.

## Indicadores do portfólio

| Indicador | Regra inicial |
|---|---|
| Projetos ativos | projetos aprovados/planejados/em execução/em espera no escopo autorizado |
| Saúde da carteira | quantidade e percentual verde/amarelo/vermelho, com `unavailable` separado |
| Projetos atrasados | fim planejado vencido e projeto não encerrado |
| Marcos vencidos | tarefa classificada como marco, vencida e incompleta |
| Marcos próximos | marcos nos próximos 30 dias, por criticidade |
| Projetos bloqueados | em espera ou com bloqueio ativo, incluindo idade do bloqueio |
| Atualização pendente | projeto ativo sem revisão dentro da cadência definida |
| Progresso | percentual do GLPI, identificando cálculo automático ou manual |
| Prazo | variação entre datas planejadas e projeção/realização |
| Custo | aprovado, comprometido/real e variação, somente quando a fonte for confiável |
| Benefícios | prometidos, medidos e pendentes após encerramento |

O painel sempre apresentará período, timestamp, cobertura, fonte e drill-down. Média de percentuais sem peso não será usada como “saúde global”.

## Visões por público

- **Executivo/stakeholder:** carteira, saúde, prazo, custo, benefícios, riscos e decisões necessárias.
- **Cliente:** apenas seus projetos autorizados, marcos, andamento, entregas e impedimentos publicáveis.
- **Governança/PMO:** intake, priorização, capacidade, qualidade cadastral, dependências, riscos e cadência.
- **Gerente de projeto:** cronograma, equipe, tarefas, custos, mudanças, bloqueios e atualizações.
- **Equipe técnica:** tarefas atribuídas, vínculos técnicos e próximos marcos, sem acesso indevido ao portfólio.

## Piloto de homologação

1. Descobrir e fixar a versão/imagem real do GLPI; a implantação atual usa tag flutuante `latest`, que não é aceitável para produção.
2. Fazer backup e validar restauração antes de configurar taxonomias ou perfis.
3. Validar Projetos, ProjectTask, equipes, Gantt, Kanban, custos, vínculos e permissões na instalação atual.
4. Criar perfis mínimos: Governança/PMO, gerente, equipe, stakeholder somente leitura e cliente somente leitura no próprio tenant.
5. Configurar estados, tipos, saúde, categorias e templates sem alterar o núcleo.
6. Selecionar até cinco projetos reais: interno, infraestrutura, sustentação, segurança e cliente, se aplicável.
7. Operar duas cadências semanais e medir completude, atualização e aderência.
8. Validar leitura pela API com conta técnica somente leitura e implementar o adaptador ness.OS.
9. Executar testes negativos de entidade/tenant antes de expor dados a clientes.
10. Fazer aceite com Governança e decidir se o GLPI se torna definitivamente canônico.

## Critérios de aceite

- cinco projetos podem ser acompanhados sem planilha paralela para o mesmo dado gerencial;
- todos os projetos ativos possuem os campos mínimos e atualização dentro da cadência;
- tarefas, responsáveis, prazos e relações ITIL/ativos funcionam no fluxo real;
- stakeholder e cliente enxergam somente o escopo autorizado;
- API entrega projetos/tarefas com paginação e conta de menor privilégio;
- painel ness.OS mostra indicadores reais, fonte, qualidade e drill-down ao GLPI;
- backup/restore, histórico e auditoria necessários são demonstrados;
- limitações remanescentes têm owner, risco e prazo.

## Gatilhos para reavaliar uma ferramenta dedicada

Reavaliar somente se o piloto provar lacunas materiais em gestão de dependências, capacidade de equipes, baseline de cronograma, gestão financeira, portfólio em escala ou colaboração externa. Nesse caso, comparar apenas soluções Community/open source e manter o ness.OS como camada de consolidação.

## Fontes oficiais

- [Projetos no GLPI](https://help.glpi-project.org/documentation/modules/tools/projects)
- [Tutorial de gestão de projetos](https://help.glpi-project.org/tutorials/tools/projects)
- [Kanban e equipes](https://help.glpi-project.org/documentation/modules/overview/kanban)
- [Relação de tickets com projetos e tarefas](https://help.glpi-project.org/documentation/modules/assistance/tickets/ticketmanagement)
- [API REST do GLPI](https://github.com/glpi-project/glpi/blob/11.0/bugfixes/apirest.md)
