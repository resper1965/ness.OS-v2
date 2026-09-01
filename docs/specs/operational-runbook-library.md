# Especificação — Biblioteca operacional de runbooks do ness.OS

> Estado: direção confirmada.
> Escopo: conhecimento acionável para operação MSP; não é repositório oficial de políticas nem sistema completo de GED/GRC.

## Decisão

No ness.OS, políticas e procedimentos serão tratados principalmente como **referência operacional para runbooks**. O conteúdo deve ajudar uma pessoa autorizada a diagnosticar, decidir, executar, validar e escalar uma ação.

| Camada | Responsabilidade | Fonte oficial? |
|---|---|---|
| Sistema documental da Ness ou do cliente | política, norma ou procedimento formal aprovado | **sim, fora do ness.OS** |
| GLPI Knowledge Base | runbooks, checklists e orientações operacionais por entidade/público | **sim para o conteúdo operacional** |
| ness.OS | pesquisa contextual, recomendação, indicadores, vigência, execução e drill-down | não; consome GLPI e links oficiais |
| Repositório do serviço | runbook estritamente ligado a código, versão ou deploy | sim para aquele runbook técnico |
| Object Storage/GLPI Documents | evidências e anexos operacionais conforme retenção | sim para a evidência correspondente |
| Psono e SOPS/age | senhas, chaves e segredos | sim para segredos; nunca incorporados ao texto |

O ness.OS não aprova nem substitui a política corporativa de nenhuma organização. Ele registra qual documento oficial fundamenta o runbook e se essa referência ainda está vigente.

## Conteúdo adequado

- diagnóstico de indisponibilidade e degradação;
- resposta a incidentes e vulnerabilidades;
- backup, restauração e continuidade;
- onboarding, offboarding e controle de acesso;
- mudança, deploy e rollback;
- triagem de alertas Zabbix/Wazuh;
- procedimentos GLPI, Authentik, Psono e demais aplicações;
- checklists de manutenção, coleta, mapas, localização e qualidade cadastral;
- comunicação e escalonamento com cliente/stakeholder.

Não pertencem à biblioteca: contratos completos, política oficial original, ata, evidência bruta de auditoria, segredo, dump, log integral ou dado pessoal sem necessidade operacional.

## Modelo MSP e isolamento

| Classe | Owner | Publicação GLPI | Visibilidade ness.OS |
|---|---|---|---|
| Runbook interno Ness | Ness | entidade/grupos internos | operadores Ness autorizados |
| Runbook padrão do serviço MSP | Ness | entidades abrangidas ou grupos operacionais | clientes veem somente a parte publicável |
| Runbook específico do cliente | Ness e/ou cliente | entidade do cliente | somente tenant e operadores autorizados |
| Orientação fornecida pelo cliente | cliente | entidade do cliente, após validação operacional | somente tenant e equipe autorizada |

Conteúdo de cliente nunca será publicado na entidade raiz do GLPI. API, busca, cache, anexos, IA e exportação deverão aplicar tenant no servidor. Filtros do navegador não são controle de acesso.

## Metadados mínimos

Todo runbook terá:

- ID e título;
- tenant/escopo e serviço relacionado;
- owner e substituto;
- audiência e classificação;
- condição de acionamento;
- criticidade e permissões necessárias;
- versão, data da última validação e próxima revisão;
- política/procedimento oficial relacionado: organização, ID, versão e URL;
- riscos, pré-condições e critérios de abortar;
- rollback/recuperação;
- evidência esperada e caminho de escalonamento;
- vínculo com alertas, itens, serviços, tickets, problemas, mudanças ou projetos;
- localização canônica quando estiver no repositório do serviço.

A biblioteca guarda referência ao documento oficial, não uma cópia apresentada como canônica.

## Estrutura obrigatória de um runbook

1. objetivo e quando usar;
2. impacto e escopo/tenant;
3. pré-condições e acessos necessários;
4. diagnóstico e evidências a coletar;
5. passos numerados, com pontos de decisão;
6. validação do resultado;
7. rollback ou contenção;
8. escalonamento, comunicação e responsáveis;
9. registro no ticket/incidente/mudança;
10. referências oficiais e histórico de teste.

Uma orientação meramente descritiva pode ser artigo de conhecimento, mas não será classificada como runbook testado.

## Ciclo de vida operacional

`draft → technical_review → approved_for_use → tested → stale/retired`

- aprovação significa adequado para uso operacional, não aprovação da política oficial;
- runbook crítico exige teste controlado ou exercício antes de receber estado `tested`;
- mudança no serviço, ferramenta ou política relacionada pode invalidar o runbook;
- conteúdo vencido permanece auditável, mas não deve ser recomendado durante incidente;
- execução deve registrar quem usou, quando, em qual tenant e qual foi o resultado, sem copiar segredos.

## Integração com GLPI e ness.OS

O GLPI 11 oferece categorias, alvos por entidade/grupo/perfil/usuário, vigência, anexos, histórico, revisões restauráveis e vínculos com objetos. Ele será a base operacional para conteúdo não acoplado a código.

O ness.OS deverá:

- sugerir runbooks a partir de serviço, ativo, alerta ou incidente;
- exibir fonte, tenant, validade, última validação e confiança;
- permitir busca apenas no escopo autorizado;
- abrir o artigo GLPI ou arquivo técnico canônico;
- registrar uso, resultado e feedback;
- impedir recomendação automática de conteúdo `stale` ou `retired`;
- nunca enviar conteúdo de um tenant ao contexto de IA de outro.

## Indicadores executivos

- serviços críticos com e sem runbook;
- alertas/incidentes críticos com runbook vinculado;
- runbooks vigentes, vencidos e próximos da revisão;
- runbooks críticos testados e taxa de sucesso do último exercício;
- tempo de localização e taxa de uso durante incidentes;
- execução com sucesso, rollback ou escalonamento;
- runbooks sem owner/substituto;
- referências a políticas oficiais vencidas ou inacessíveis;
- divergência entre artigo GLPI e runbook técnico do repositório;
- cobertura e qualidade por cliente, sem comparação indevida entre tenants.

## Piloto inicial

Publicar e testar 8–12 runbooks:

1. indisponibilidade Zabbix;
2. indisponibilidade AIOps/GLPI;
3. falha de backup e restauração;
4. acesso privilegiado/break-glass;
5. onboarding e offboarding;
6. incidente crítico de infraestrutura;
7. incidente crítico de segurança;
8. mudança e rollback;
9. agente sem comunicação/inventário;
10. comunicação e escalonamento ao cliente.

Incluir ao menos um runbook interno Ness, um padrão MSP e um específico de cliente usando identidades descartáveis.

## Critérios de aceite

- GLPI restringe corretamente conteúdo interno e de dois tenants de teste;
- nenhum conteúdo de cliente aparece na entidade raiz, busca, link direto, cache, IA ou exportação de outro tenant;
- todos os runbooks críticos têm owner, validade, rollback, escalonamento e teste registrado;
- referência à política oficial contém organização, ID, versão e URL, sem alegar que o ness.OS é a fonte;
- runbook vencido não é recomendado como vigente;
- restauração das revisões e anexos operacionais é demonstrada;
- dashboard mostra cobertura, validade, teste, uso e qualidade;
- nenhum segredo ou evidência sensível indevida está no texto.

## Fontes oficiais consultadas

- [Knowledge Base do GLPI](https://help.glpi-project.org/documentation/modules/tools/knowledgebase)
- [Vinculação de artigos a objetos](https://help.glpi-project.org/documentation/tabs/knowledgebase)
- [Gestão de documentos no GLPI](https://help.glpi-project.org/documentation/modules/management/documents)
