# Contexto canônico — ness.OS

Atualizado em: 2026-10-12 (BRT)
Estado: execução retomada; G0 tem promoção real do Hub/AIOps comprovada, mas
permanece **PARCIAL** até CI limpo e integração protegida do workflow.

Retomada pelo modelo executor em 13/10 UTC: início da proteção de entidade
efetiva no cliente GLPI do Hub. Código e testes locais verificados; ainda sem
deploy ou reativação da conta técnica 106. Ver ledger do plano master em
`.superpowers/sdd/2026-10-12-ness-os-plano-master/progress.md` e o registro
operacional GLPI. A antiga restrição “somente planejamento” foi substituída
pela autorização explícita de execução; gates e janela continuam vigentes.

T03 GLPI, 13/10 06:40 UTC: ensaios isolados confirmaram que `forward_auth`
bem-sucedido deixa a API pública alcançar o upstream e que uma rede privada
pode ser anexada a um contêiner em execução sem recriá-lo. Os ensaios não
alteraram produção; detalhes e limites na [ADR 0020](adr/0020-glpi-maintenance-entity-boundary.md).
A conta técnica 106 permanece inativa, sem ativos novos. A fronteira direta,
SSO/rota real e configuração durável ainda não foram aprovadas; a issue #76
continua pré-requisito para qualquer recriação do contêiner GLPI.

## Ponto único de retomada — plano master

Destino atualizado por instrução humana: **produção completa**, cobrindo todas
as entidades/ativos existentes e fases de operação assistida/segurança. Piloto
interno é somente canário; não encerrar no MVP. A execução está autorizada na
branch de entrega; aplicam-se os gates específicos, sem dispensar segurança.

[Plano master ness.OS](superpowers/plans/2026-10-12-ness-os-plano-master.md)
consolida sequência, decisões e aceites; planos de produto detalham tarefas e
registros de execução mantêm evidências. A continuação automática do plano
master foi reativada; isso não renova a janela histórica de mutações.
As prioridades e números abaixo são históricos onde divergem dos registros
de 12/10; retomar pelo master e pelo último resultado da ferramenta foco.

## Propósito

### Retomada GLPI — 13/10/2026 (execução do master)

No checkout `feat/incidents-rbac-local`, o cliente do Hub passou a conferir a
entidade efetiva após `changeActiveEntities`, a percorrer toda a paginação da
busca de ticket por marcador e a classificar 401/403 como falha permanente.
A entrega seguinte classifica falhas de transporte, HTTP 429 e 5xx como
transitórias e aplica retry exponencial limitado (30–900 s, 12 tentativas),
sem ampliar permissões. A seleção de entidade também classifica queda de
transporte e encerra a sessão. Ao esgotar 12 retries, o worker mantém a
falha visível e registra ação `ticket_retry_exhausted` sem payload. Suíte
backend: 426 PASS, 1 SKIP; classificador: 3 PASS. Nenhuma dessas
alterações foi promovida ao runtime produtivo.

Concorrência T04: release candidata usa `pg_advisory_xact_lock` por entidade
e fingerprint durante busca/criação de ticket, com espera máxima de 15 s e
falha transitória em timeout. Ensaio de dois workers simulados e sonda de
bloqueio no PostgreSQL real, sem escrita, passaram. Suíte backend: 428 PASS,
1 SKIP. A busca GLPI após POST ainda exige canário real antes de aprovar
idempotência de ponta a ponta.

Após o repositório tornar-se público, os cinco jobs do PR #64 iniciaram.
No commit `433c710`, Secret scan, Frontend CI, SBOM e Lint/Type passaram.
Backend CI alcançou o fluxo integrado descartável e revelou que seu mock não
respondia ao novo `getActiveEntities`; o mock foi atualizado, sem relaxar a
verificação de entidade. No commit `609e296`, o fluxo PostgreSQL/Redis passou
no Actions, assim como os outros quatro jobs; o Backend CI parou depois num
fixture de preflight sem `NINF_API_IMAGE` e `NINF_FRONTEND_IMAGE`. O fixture foi
completado com referências fictícias e seu teste local passou. Novo run remoto
é necessário; G0 permanece pendente.
O teste separado de preflight também assumia sete variáveis obrigatórias,
quando o Compose exige nove; seus fixtures foram atualizados e ambos os
testes de readiness/preflight passaram localmente. A suíte de histórico,
relatório de integração e payload n8n também passou; ainda falta CI remoto.
No commit `dbf4596`, os cinco jobs remotos passaram: Secret scan, Lint/Type,
SBOM, Backend CI e Frontend CI. O Backend CI incluiu o fluxo PostgreSQL/Redis,
preflight, Compose e payload n8n. PR #64 segue draft, `REVIEW_REQUIRED` e
`BLOCKED`; CI verde não aprova G0 ou promoção produtiva.

Para GLPI, a [ADR 0020](adr/0020-glpi-maintenance-entity-boundary.md) registra
uma direção de protótipo para isolar a conta técnica 106, que continua inativa.
O desenho não é aprovação nem substitui testes negativos diretos da API.
Ensaio sintético válido em 13/10 confirmou a falha: usuário somente na entidade
pai, perfil mínimo e grant não recursivo recebeu HTTP 200 para Computer da
filha após `changeActiveEntities`; antes recebeu 403. O mesmo ocorreu por
`user_token`. Filtro IP/App-Token negou o Hub simulado, mas não conteve a
troca de entidade na sessão do adaptador. O primeiro fixture tinha hierarquia
não validada e foi descartado. T03/G2 seguem bloqueados; 106 não foi reativada.
Topologia frontal/privada passou em laboratório Docker descartável; política
de leitura restrita de Computer passou em 13 testes, incluindo falha segura
se o encerramento da sessão GLPI falha. Uma rota FastAPI privada
independente passou em 15 testes, inclusive falha upstream sanitizada, mas não
está conectada ao runtime nem implantada. A suíte backend total passou em
456 testes, 1 pulado. Isso não
isola a API produtiva nem autoriza criar os três ativos pendentes.
Quedas de transporte durante `get_item` e `list_items` no cliente compartilhado
agora são classificadas como transitórias; testes RED reproduziram os
`ConnectError` crus e a suíte backend passou depois em 458 testes, 1 pulado.
Ainda sem deploy.
Na listagem de subitens, o cliente agora segue o total informado pelo GLPI
mesmo quando o servidor limita a página a 50 registros e recusa página vazia
antes do total. Os dois testes RED→GREEN e a suíte backend passaram em 460
testes, 1 pulado. Ainda não houve canário real nem promoção.
Sonda sem credenciais no runtime confirmou uma rede compartilhada entre
`ninf-api` e `ninf-glpi` (`BLOCKED_DIRECT_PATH`); a issue #74 foi corrigida
com esse bloqueio e a instrução de manter 106 inativa.
Um ensaio Docker descartável em 13/10 04:01 UTC mostrou GLPI sintético
dual-homed, Hub na rede frontal e adaptador na privada: ambos mantiveram
seus caminhos próprios, com IPs de origem distintos; os recursos de teste
foram removidos. Não testou token, API GLPI nem rota pública autenticada e
não alterou a topologia produtiva. A ADR 0020 contém a matriz e o limite.
Ensaio seguinte com GLPI 11.0.8 descartável e cliente API sintético limitado
ao IP privado confirmou login pelo adaptador HTTP 200 versus Hub frontal 400;
replay da sessão, cabeçalho de origem forjado e login sem App-Token no frontal
também foram negados. Recursos temporários removidos. Falta provar Caddy
autenticado, IP estável, operações de objeto e o Compose produtivo; 106 segue
inativa, T03/G2 não aprovados.
Preflight somente leitura da topologia produtiva encontrou outra dependência
para T03: a imagem GLPI usa `/var/glpi` num volume anônimo com configuração e
arquivos, enquanto o Compose versionado monta `app_glpi-data` em
`/var/www/html/glpi`. Não recriar o container com esse Compose antes de
migrar/preservar o estado de `/var/glpi` e testar retorno; ADR 0020 detalha.
Um guard de pré-deploy versionado bloqueia a recriação quando o volume
de `/var/glpi` no Compose não é o mesmo em execução; passou nos testes e
bloqueou o Compose produtivo atual em leitura, sem alterar dados. Issue #76
continua aberta para migração reversível.
Um comparador offline versionado verifica conteúdo e metadados entre o volume
original e o novo sem expor caminhos ou dados; falta a janela de cópia/corte,
bloqueio de escrita, readback e rollback efetivo.
Um laboratório descartável no mesmo host validou cópia `cp -a`, comparação
do volume sintético e reanexação somente leitura do original; resíduos do
teste foram removidos. A etapa produtiva exige janela e rota de manutenção
que impeça escritas durante o corte, além de teste de retorno completo.
Um candidato de Caddy para manutenção exclusiva do GLPI foi gerado com
precondição de hash e validado sem deploy; laboratório descartável confirmou
503 GET/POST no host GLPI e 200 nos hosts Hub/SSO sintéticos. Procedimento
e limites estão em `docs/operations/glpi-state-volume-cutover-2026-10-13.md`.
No fluxo de incidentes para tickets, um teste RED mostrou que o log INFO
continha toda a análise de IA. A mensagem passou a registrar apenas a conclusão,
sem conteúdo da análise; 95 testes focados e 456 testes backend passaram.
Ainda é alteração de código não promovida ao runtime produtivo.

Diagnóstico somente leitura encontrou 159 incidentes sem ticket: 115 antigos
sem falha registrada, 29 recentes com `ticket_failed` não classificado e 15
sem ID de evento de origem. Os 29 surgiram na hora 02:00 UTC e o worker
registrou 116 erros `ConnectError`, compatíveis com quatro tentativas por
incidente; não está provada a causa raiz da interrupção. Sonda de leitura
GLPI voltou a `ready`, mas não comprova escrita. O classificador paginado
somente leitura confirmou as 159 entradas em 13/10 02:20 UTC; cursor final
76656 e sem página adicional. Não houve replay em massa.
O usuário técnico GLPI 106 segue inativo pelo teste negativo de isolamento;
G2 e a promoção de release continuam abertos. Próximo: reconciliador de
backlog em dry-run, isolamento nativo estrito e só então ensaio controlado
de escrita/idempotência, release e promoção.

Preflight T07 em 13/10 06:18 UTC: inventário nativo GLPI está desativado
(`enabled_inventory=0`). Os sete registros de agente tiveram último contato
em julho; seis têm padrão de varredura e nenhum desses seis vínculo a ativo.
GET interno da rota de inventário retornou 403; GET público sem sessão
redirecionou ao Authentik. Isso não é teste de POST de agente. Não contar os
sete como frota operacional nem abrir exceção pública sem testar autenticação,
origem e rejeição; plano de cinco ativos internos permanece pendente.

O ness.OS é a camada operacional que reúne monitoramento, ITSM, automação e
SecOps em uma experiência segura por tenant. O primeiro produto aceito é o
fluxo autenticado:

```text
Zabbix -> incidente no Hub -> ticket GLPI -> acompanhamento e encerramento
```

Wazuh, Google Workspace, automações ampliadas e painéis executivos entram após
esse fluxo, não como pré-requisito para o MVP.

## Fontes canônicas

Prioridade e sequência: `docs/superpowers/plans/2026-10-12-ness-os-plano-master.md`.
Trilha dinâmica e cartão Z1 preservam histórico; não relançar esse cartão se
o ledger comprovar conclusão. Backup segue em trilha auxiliar, sem repetir
verificações sem mudança relevante.

| Tema | Documento de referência |
| --- | --- |
| Estado do MVP e evidências recentes | `docs/execution/project-stage-2026-09-28.md` |
| Plano por ativo e gates | `docs/execution/ness-os-asset-activation-master-plan-2026-08-28.md` |
| Matriz de pendências | `docs/execution/goal-completion-audit-2026-09-08.md` |
| Recuperação e release | `docs/execution/gates/phase-0-recovery-release.md` |
| Evidência da promoção Hub/AIOps | `docs/execution/evidence/hub-immutable-release-2026-10-12.md` |
| Recuperação externa atual do Hub/AIOps | `docs/execution/evidence/hub-aiops-recovery-2026-10-12.md` |
| Inventário de identidade atual | `docs/execution/evidence/authentik-g2-readonly-inventory-2026-10-12.md` |
| Recuperação atual do Psono | `docs/execution/evidence/psono-recovery-2026-10-12.md` |
| Plano de execução atual | `docs/execution/dynamic-delivery-track-2026-10-12.md` |

Documentos históricos permanecem como evidência; não substituem uma validação
atual de ambiente, credenciais, backup ou serviço.

## Estado consolidado

Execução independente em 12/10: ensaio isolado com PostgreSQL/Redis reais
aprovado para retry GLPI, três replays, auditoria e tenant; APIs externas
simuladas. Baseline de qualidade renovada no Zabbix isolado, com 2.887 itens
não suportados históricos. Evidências: `hub-isolated-flow-2026-10-12.md` e
`zabbix-offline-quality-2026-10-12.md` em `docs/execution/evidence`.

| Componente | Situação | Próximo gate |
| --- | --- | --- |
| Repositório e release | branch de entrega sincronizada; Hub/AIOps promovido com imagens GHCR por digest e rollback ensaiado | CI limpo e integração protegida do workflow antes de aprovar G0 global |
| Zabbix | destino permanente restaurado em UAT isolada; origem é rollback | revalidar estado atual, UAT de identidade e piloto Cavan antes de corte |
| Object Storage/Restic | conjunto AIOps de 12/10/2026 08:55 BRT copiado, verificado e restaurado externamente | repetir a evidência atual para os demais produtores e revisar 3-2-1 |
| Hub | runtime real promovido, `/ready` aprovado, workers saudáveis e rollback/re-promoção ensaiados | recuperação atual e MVP Authentik + Zabbix + GLPI reais |
| GLPI | fundação, catálogo e reconciliação parcial prontos | API de máquina e jornada de ticket ponta a ponta |
| Authentik | runtime saudável; `platform_admin` contém Ismael, Rogerio e Ricardo; MFA ainda não comprovado | MFA, recuperação, revogação e teste por aplicação/tenant |
| Psono Community | recuperação externa atual aprovada na AIOps | dois custodians, MFA, SMTP/recovery e promoção dedicada |
| AIOps | backup/restore comprovados; operação ainda não homologada | contratos, fluxos de incidente e observabilidade |
| Wazuh | planejado | capacidade, arquitetura hub-spoke e piloto isolado |

## Regras permanentes

Decisão de 12/10/2026: G2 fica aberto em issues, sem impedir desenvolvimento,
ensaios isolados e tarefas independentes. Toda interação humana exige issue
com passo a passo e e-mail ao responsável; continuar sem aguardar resposta
nas demais tarefas. Índice: issue #68 e
`docs/execution/human-actions-and-independent-delivery-2026-10-12.md`.

1. A origem Zabbix não é alterada durante a migração sem rollback comprovado.
2. Nenhum segredo, token, senha, chave privada ou dump entra no Git.
3. Toda alteração produtiva tem backup, rollback, owner e evidência posterior.
4. Dados de tenant só aparecem no Hub quando origem, escopo e frescor forem
   comprovados; indisponibilidade nunca vira zero ou saudável.
5. Ações corretivas, notificações, agentes, proxies e DNS só são ativados no
   gate explicitamente aprovado.
6. Branding vem após estabilidade funcional e usa a base ness.: Montserrat 500,
   caixa baixa e ponto BlueDot `#00ade8`.

## Localização do projeto

- WSL: `/home/resper/ness.OS`
- Windows: `\\wsl.localhost\\Ubuntu\\home\\resper\\ness.OS`
- Git remoto: `https://github.com/resper1965/n-infraops.git`

Arquivos temporários de execução não pertencem ao checkout. Os encontrados em
2026-10-11 foram preservados em quarentena externa, com checksum, antes da
sincronização do Git.
