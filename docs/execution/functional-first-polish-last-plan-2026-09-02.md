# Plano de implantação funcional e polimento final — 02/09/2026

## Decisão de execução

O programa será conduzido em duas passagens:

1. **implantação funcional:** concluir infraestrutura, identidade, dados reais,
   integrações, segurança, recuperação e operação ponta a ponta;
2. **polimento final:** retornar a cada aplicação para aplicar identidade visual,
   aperfeiçoar UX, textos, responsividade e consistência entre produtos.

O polimento não bloqueia a implantação. Segurança, acessibilidade mínima,
clareza de erro, desempenho necessário ao uso, backup e correções funcionais
não são polimento e permanecem obrigatórios em cada onda.

```text
Zabbix confiável
  -> identidade e cofre funcionais
  -> GLPI/CMDB operacional
  -> hub e fluxo ponta a ponta
  -> AIOps e automações controladas
  -> SecOps piloto
  -> operação e recuperação comprovadas
  -> polimento final por aplicação
```

## Regras de avanço

Cada onda segue o mesmo ciclo: `baseline -> mudança reversível -> teste positivo
e negativo -> evidência -> aceite provisório -> próxima onda`.

- Uma onda pode preparar dependências da próxima, mas não promover funções que
  dependam de um gate ainda aberto.
- Dados sintéticos nunca serão apresentados como dados reais.
- Canais reais de notificação e automações corretivas permanecem desligados até
  teste sintético, deduplicação, owner e rollback aprovados.
- Mudanças destrutivas, exclusão de histórico e retirada de caminhos antigos
  exigem uma etapa de contração separada.
- O piloto Cavan — Matriz será a referência antes da expansão a outros clientes.
- Defeitos de segurança ou uso que impeçam homologação são corrigidos na onda;
  preferências estéticas entram no backlog de polimento.

## Onda F1 — estabilizar o Zabbix e o piloto Cavan

**Objetivo:** tornar a monitoração atual confiável antes de alimentar outras
camadas.

1. concluir a primeira coleta do FortiGate interno `172.29.0.254` e do switch
   Aruba pelo proxy Cavan;
2. identificar o modelo do Aruba e selecionar template compatível;
3. separar o host único do firewall dos testes de conectividade AmericaNet e
   Vivo, mantendo histórico e rollback;
4. tratar fila, itens não suportados e idade da última coleta por causa;
5. fechar tags, localização, owner, função e criticidade dos 14 ativos Cavan;
6. validar dashboard técnico, mapa, disponibilidade e problemas atuais;
7. executar alerta sintético sem canais reais e testar recuperação;
8. só então preparar reativação controlada de ações e mídias.

**Gate F1:** dados atuais; proxies estáveis; fila sem crescimento persistente;
piloto 100% classificado; problemas conhecidos separados de falhas históricas;
nenhuma notificação indevida.

## Onda F2 — identidade, acesso e cofre

**Objetivo:** estabilizar o acesso humano e retirar segredos de arquivos
temporários antes de ampliar integrações.

1. homologar Authentik em Zabbix, GLPI, hub e ferramentas administrativas;
2. testar login, logout, MFA, expiração, revogação, usuário desativado e
   break-glass por aplicação;
3. concluir o Psono funcional: usuários, troca de senha, MFA, recuperação,
   SMTP, backup e restore;
4. definir dois responsáveis de recuperação e guardar códigos de emergência
   fora do ambiente principal;
5. migrar segredos por consumidor, validar e revogar o segredo anterior;
6. manter RBAC e segregação de tenant no backend, não apenas na interface.

**Gate F2:** acessos nominais reproduzíveis; duas recuperações independentes;
MFA privilegiado; nenhum segredo válido no Git; rollback de identidade testado.

## Onda F3 — GLPI, CMDB e inventário

**Objetivo:** estabelecer a fonte canônica de ativos, serviço e trabalho.

1. tornar a API de máquina do GLPI funcional sem contornar autorização;
2. aplicar entidades, perfis, catálogo, SLAs, projetos, tarefas e runbooks;
3. carregar o inventário Cavan e reconciliar com hosts do Zabbix;
4. ativar GLPI Agent somente no piloto;
5. relacionar ativo, local, serviço, owner, contrato e criticidade;
6. provar abertura, atribuição, atualização e encerramento de ticket.

**Gate F3:** CMDB do piloto reconciliada; acesso cross-tenant negado; importação
idempotente; histórico e rollback preservados.

## Onda F4 — núcleo do hub e fluxo operacional

**Objetivo:** entregar uma jornada real de operação, sem indicadores fictícios.

1. validar PostgreSQL, Redis, migrations, API, Celery e frontend;
2. tornar healthchecks fail-closed e medir latência, erros e filas;
3. corrigir credenciais e contratos Zabbix -> hub e GLPI -> hub;
4. implementar ingestão, deduplicação, correlação e idempotência;
5. executar o fluxo `Zabbix -> incidente -> GLPI -> hub -> encerramento`;
6. validar sessão, RBAC, tenant, logout e indisponibilidade de dependências;
7. publicar apenas leituras cuja proveniência e atualidade sejam verificáveis.

**Gate F4:** um incidente sintético percorre todo o fluxo uma única vez, no
tenant correto, com auditoria, retry controlado e atualização no portal.

## Onda F5 — AIOps, orquestração e canais

**Objetivo:** automatizar somente um fluxo já funcional e observável.

1. classificar eventos antes de qualquer automação corretiva;
2. implementar RCA assistida e sugestão de runbook com aprovação humana;
3. migrar n8n para Node-RED fluxo a fluxo, com execução paralela controlada;
4. integrar Datto/RMM e outras fontes aprovadas por contratos idempotentes;
5. habilitar Evolution/WhatsApp apenas para uma jornada testada e autorizada;
6. integrar Gemini e MISP sem enviar segredos ou dados de outro tenant;
7. medir duplicidade, latência, fila, falha, custo e taxa de intervenção humana.

**Gate F5:** retry não duplica incidentes ou tickets; falha externa degrada sem
paralisar o núcleo; toda automação possui owner, auditoria e desligamento rápido.

## Onda F6 — SecOps piloto e expansão

**Objetivo:** adicionar segurança operacional sem comprometer NOC/ITSM.

1. implantar Wazuh em topologia isolada e recuperável;
2. pilotar endpoints Cavan com RBAC e retenção definidos;
3. integrar Google Workspace em leitura mínima, inicialmente sem Alert Center;
4. normalizar eventos no fluxo de incidente já aprovado;
5. testar isolamento entre clientes e perda de conectividade;
6. medir EPS, filas, armazenamento e custo antes de escalar.

**Gate F6:** piloto isolado, recuperável, sem vazamento cross-tenant e sem
degradação das ondas funcionais anteriores.

## Onda F7 — operação, release e continuidade

**Objetivo:** tornar o conjunto sustentável e reconstruível.

1. reconciliar Git, IaC e configuração efetiva;
2. fechar CI com testes, lint, secret scan, SBOM e imagens por digest;
3. comprovar backup, restore, RPO, RTO e DR de cada sistema canônico;
4. definir SLO, owner, runbook e alerta para cada serviço crítico;
5. testar capacidade, dependência indisponível e rollback de release;
6. executar aceite operacional D+1, D+3 e D+7.

**Gate F7:** release reproduzível; restore comprovado; falhas detectadas antes
do usuário; riscos residuais formalmente registrados.

## Passagem P — polimento final por aplicação

A passagem de polimento começa somente após F1–F7 ou por exceção formal para
uma aplicação já funcional e congelada. A ordem reduz retrabalho:

1. **fundação visual compartilhada:** tokens, Montserrat 500, grid de 8 px,
   BlueDot `#00ade8`, favicon, iconografia, estados e acessibilidade;
2. **Authentik:** login, recuperação, MFA, consentimento, erros e catálogo de
   aplicações;
3. **Psono:** marca, título do navegador `vault ness.`, login, cofre, MFA e
   mensagens de recuperação;
4. **Zabbix:** navegação, dashboards por público, mapas, títulos, densidade,
   empty states e experiência móvel;
5. **GLPI:** portal, catálogo, tickets, conhecimento e visão do cliente;
6. **hub:** visão executiva, operação, incidentes, inventário, projetos e PWA;
7. **ferramentas operacionais:** Node-RED, observabilidade e consoles internos;
8. **revisão transversal:** consistência visual, linguagem pt-BR, desempenho,
   responsividade, contraste e jornada ponta a ponta.

Toda representação visual da marca `ness.` deve manter caixa baixa, Montserrat
500, lettering preto ou branco e ponto separado em BlueDot `#00ade8`. O logo
fica isolado, sem tagline ou razão social. Cada customização deve ser externa
ao core do produto, versionada, reversível e revalidada após upgrades.

**Gate P:** checklist visual aprovado em desktop e mobile; nenhuma regressão de
segurança ou função; rollback de tema testado; experiência coerente entre as
aplicações.

## Quadro de controle

| Onda | Estado em 02/09/2026 | Saída para avançar |
| --- | --- | --- |
| F1 — Zabbix/Cavan | em execução | coleta interna, qualidade e alerta sintético |
| F2 — identidade/cofre | parcialmente implantada | jornadas e recuperação aprovadas |
| F3 — GLPI/CMDB | em execução; API, taxonomia e metadados Cavan reconciliados | fluxo de ticket comprovado e agente piloto protegido |
| F4 — hub/fluxo | núcleo disponível; leituras GLPI/Zabbix aprovadas | fluxo ponta a ponta comprovado |
| F5 — AIOps/canais | preparação | automação idempotente e degradável |
| F6 — SecOps | planejamento/piloto | isolamento e capacidade comprovados |
| F7 — operação/release | transversal incompleta | restore, SLO e release aprovados |
| P — polimento | backlog controlado | revisão visual e UX final |

## Próxima fila executável

1. observar a sincronização do proxy Cavan para o FortiGate LAN e o Aruba;
2. concluir a modelagem firewall versus links no Zabbix;
3. reduzir o núcleo persistente da fila e classificar itens não suportados;
4. fechar alerta sintético e recuperação do piloto;
5. concluir F2 pelo teste completo de acesso, MFA e recuperação do Psono;
6. concluir o desenho autenticado do GLPI Agent antes de reabrir o inventário;
7. provar o ciclo de ticket GLPI e, em seguida, o incidente ponta a ponta no hub;
8. validar deduplicação, retry e isolamento de tenant no fluxo integrado;
9. seguir onda a onda sem abrir a passagem de polimento antes do gate funcional.

## Critério de conclusão do programa

Atualização de 08/09/2026: a etapa local de deduplicação e retry hub/GLPI foi
validada com 162 testes do backend. Evidência e limites em
[hub-glpi-retry-validation-2026-09-08.md](hub-glpi-retry-validation-2026-09-08.md).
Essa pendência foi superada para o ciclo técnico de ingestão e resolução em
08/09/2026: implantação expandida a 256 hosts mapeados, abertura real de tickets,
callback de resolução e reconhecimento do evento original comprovados. Evidências,
rollback e limites em
[hub-glpi-production-rollout-2026-09-08.md](hub-glpi-production-rollout-2026-09-08.md).
Por orientação do responsável, a expansão hub/GLPI não depende mais de piloto
separado. As demais jornadas de F4 e ondas do programa mantêm seus critérios;
não são declaradas concluídas por essa validação técnica.

O programa termina quando F1–F7 e P estiverem aprovadas, o fluxo técnico e de
serviço estiver comprovado para Cavan, cada sistema puder ser restaurado e as
customizações visuais puderem ser removidas sem afetar dados ou operação.
