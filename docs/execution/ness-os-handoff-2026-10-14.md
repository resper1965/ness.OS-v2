# ness.OS — handoff para retomada por outro modelo

Checkpoint: **14/10/2026, manhã BRT**. Este documento é uma orientação de
retomada, não telemetria nem aceite de produção. O último indicador factual foi
verificado em **13/10/2026, 22:40 BRT**. Antes de agir, ler, nesta ordem:

1. [Plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md).
2. [Indicador datado](ness-os-status.md) — prevalece sobre este handoff se houver
   atualização posterior.
3. [Contexto canônico](../PROJECT_CONTEXT.md) e
   [ledger](../../.superpowers/sdd/2026-10-12-ness-os-plano-master/progress.md).
4. [GLPI próxima entrega](glpi-next-delivery-2026-10-12.md) e
   [ADR de isolamento](../adr/0020-glpi-maintenance-entity-boundary.md) para T03.

## Objetivo e estado global

O produto final integra Authentik (identidade), Psono (cofre), Zabbix
(monitoração), GLPI (CMDB/ITSM), Hub/PWA (experiência e orquestração), AIOps,
Node-RED e Wazuh/Workspace, com isolamento por tenant e marca ness. O canário
de 5–10 ativos é o começo da expansão, **não** o aceite global. A meta é
cobrir entidades e ativos existentes elegíveis, com evento → incidente →
ticket e operação recuperável.

**Produção completa: não liberada.** F0 release, F1 identidade/cofre, F2
Zabbix, F3 GLPI, F4 Hub, F6 AIOps e F8 marca estão parciais; F5 operação
integrada e F7 segurança não têm aceite completo. Nenhum gate global G0–G5
deve ser inferido de CI verde, serviço `running`, UAT ou documentação. O
indicador registra os detalhes por fase sem porcentagens inventadas.

## Foco e bloqueios vigentes

### GLPI T03 — isolamento da rota direta

- A conta técnica **106 permanece desativada**. A API nativa permitiu à
  identidade não recursiva da entidade 1 selecionar a descendente 5 e ler um
  Computer dela. O laboratório corrigido reproduziu a falha de escopo.
- O filtro nativo por `REMOTE_ADDR`/App-Token e o bloqueio público Caddy não
  isolam a rota interna: Hub/API e GLPI ainda compartilham `ninf-net`. O
  gateway privado é **candidato não implantado**; seu Compose opt-in ainda
  mantém caminho direto. Os testes unitários e o ensaio de rede sintética
  não substituem a matriz negativa no runtime real.
- Não reativar 106, não gerar token e não criar os três ativos pendentes
  (10983/10984/10987) até provar bloqueio da rota direta e da pública
  autenticada, IDOR/search/export/batch/replay, entidade descendente e
  rollback. PR #64 segue draft, sem deploy. Issues #67/#74 e ADR 0020
  guardam o contrato e a matriz.
- Trabalho independente já entregue na branch inclui volume persistente
  `/var/glpi`, guarda pública, paginação, gateway fail-closed e reserva
  idempotente T04. A última correção T04 (`13a5720`) evita consumir reserva
  quando a busca inicial falha antes de qualquer POST. Falha após o claim
  continua exigindo reconciliação; não reenviar automaticamente. Não houve
  migração do esquema T04, deploy ou replay produtivo.
- Deduplicação em massa de 33 pares de login ativo/ativo aguarda decisão RBAC
  da issue #77; perfis legado/LDAP divergem. Não copiar grants nem apagar
  usuários automaticamente. Tema ness. ainda requer login/inspeção nominal.
  Agentes de inventário estão sem contato desde julho; piloto depende da
  identidade e negativa de associação cruzada da issue #79. Plugins residuais
  não foram removidos por ausência de prova de dependências/dados.

### F0 — CI local substituindo GitHub Actions

- Por cobrança, GitHub Actions está **desativado**. Repositório privado atual:
  `resper1965/ness.OS-v2` (nomes/remotos antigos em planos históricos não
  prevalecem). A `main` mantém PR obrigatório, proteção a admins e quatro
  checks vinculados ao app Actions (`app_id=15368`); não remover nem reativar
  Actions sem substituto seguro comprovado.
- PR #81 `no-actions-release` segue draft. Builder local passou checks
  completos/scan e publicou API/frontend no GHCR privado, com pull por
  digest. Isso **não** equivale a deploy ou check externo. O runner candidato
  `/opt/ness-ci` foi instalado root-owned fora do PR e executou backend,
  qualidade, scanner e frontend em contêineres sem rede/socket/chave.
- App privada `ness-os-local-ci` (ID 5307771; instalação 171160625) existe
  só no repo. A chave nova está fora do Git em arquivo root-only; a primeira
  chave ainda aparece ativa e sua revogação segue pendente. **Não abrir,
  copiar ou imprimir chaves/tokens.** A App ainda precisa de `Pull requests:
  Read-only` e readback do `head.sha` remoto para vincular evidência ao PR.
- Bloqueio crítico: `resper` está no grupo `docker`; o socket é
  `root:docker 0660`. Acesso ao daemon concede privilégio equivalente a root,
  então `root:root 0600` no mesmo host/domínio **não prova separação** entre
  builder e signer. Não criar/ativar emissor co-localizado, não emitir checks
  nem mudar a proteção da `main` até separar o signer do domínio do Docker
  (ou comprovar isolamento equivalente), testar negativa de leitura pelo
  builder, validar SHA/evidência e falhas negativas ponta a ponta.
- Histórico de heads/tags foi sanitizado após rotação de credenciais; refs
  de PR/caches antigos ainda requerem GitHub Support (issue #82). Restore
  externo isolado pós-rotação terminou `exit 0`, PASS para o mesmo conjunto;
  **não repetir** sem mudança relevante. Não publicar valor secreto em Git,
  chat, issue, email ou saída de ferramenta.

### F2 — Zabbix

Origem permanece **única coletora**; destino restaurado, isolado e mascarado.
Referência de escopo: 262 hosts reais + 63 protótipos (protótipos não são
ativos). Última amostra citada: 2,086% unsupported. O token de manutenção
anterior expirou. Janela de mutações até **15/10/2026 11:47:35 BRT**; a
extensão não renova credencial nem aprova corte. Não alterar DNS, fazer dupla
coleta ou desmascarar destino antes de gates G0/G1/G2 aplicáveis, qualidade,
freeze, snapshot final, GO formal e rollback. Após o prazo, nenhuma mutação
Zabbix sem nova autorização. Não refazer restore/importação/probes já aprovados
sem delta; probes Windows disabled devem permanecer assim.

## Próxima sequência segura

1. Conferir indicador, ledger, horário, `git status` e últimos resultados de
   cada checkout. Se nada mudou, **não** regravar estado nem repetir auditoria.
2. Foco principal GLPI T03. Desenhar e ensaiar **separação efetiva** entre
   Hub/API e GLPI, preservando UI/SSO/DB e retorno. Só propor deploy após
   prova negativa da rota direta e matriz da ADR 0020; 106 fica desativada.
3. Em paralelo apenas como pré-requisito de release, resolver domínio separado
   do signer local, permissão mínima da App, leitura do PR head e testes
   negativos. Somente após prova ponta a ponta considerar troca controlada
   dos quatro checks, revisão dos PRs e merge. Imagem por digest não é GO.
4. Enquanto T03 estiver bloqueado, avançar uma entrega GLPI independente e
   reversível por vez. Manter identidade, SLA/tenant e permissões como fatos
   confirmados; sem SQL de configuração para contornar API/403.
5. Atualizar indicador e ledger só ao mudar entrega, gate, bloqueio, foco ou
   prazo; teste/readback pertinente, commit coerente e push. Durante trabalho
   ativo, informar tarefa/resultado/próximo passo em até 60 s. Recorrência
   inalterada fica silenciosa; pedir ação humana apenas se indispensável e
   ainda não registrada.

## Checkouts e evidências de código

| Checkout | Branch | Uso |
|---|---|---|
| `/home/resper/ness.OS` | conferir antes de editar | Plano master, contexto e ledger operacional. |
| `/home/resper/ness.OS-clean` | `feat/incidents-rbac-local` | GLPI, ADR e indicador; último commit visto `94bff71`, árvore limpa neste checkpoint. |
| `/home/resper/ness.OS-release` | `no-actions-release` | PR #81 e CI local; último commit visto `0b7abec`, árvore limpa neste checkpoint. |

Evidência local/testes é **candidata** até promoção e readback real. Não
reinterpretar um commit, um PR draft ou um backup PASS como aprovação de um
gate inteiro. O usuário autorizou execução do plano master e pequenas decisões
em escopo, não a dispensa de isolamento, segurança, GO de corte ou custos.
