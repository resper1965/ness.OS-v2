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

## Ponto único de retomada — plano master

Destino atualizado por instrução humana: **produção completa**, cobrindo todas
as entidades/ativos existentes e fases de operação assistida/segurança. Piloto
interno é somente canário; não encerrar no MVP. Planejamento continua sem execução
pelo modelo autor. Aplicam-se os gates específicos, sem dispensar segurança.

[Plano master ness.OS](superpowers/plans/2026-10-12-ness-os-plano-master.md)
consolida sequência, decisões e aceites; planos de produto detalham tarefas e
registros de execução mantêm evidências. Planejamento concluído, sem execução
por seu modelo autor, conforme instrução humana. Automação permanece pausada.
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

Para GLPI, a [ADR 0020](adr/0020-glpi-maintenance-entity-boundary.md) registra
uma direção de protótipo para isolar a conta técnica 106, que continua inativa.
O desenho não é aprovação nem substitui testes negativos diretos da API.

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
