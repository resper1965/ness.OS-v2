# ness.OS — handoff de desenvolvimento (22/10/2026)

Este documento permite retomar o trabalho sem a conversa anterior. É um
checkpoint, não uma auditoria em tempo real nem autorização de mudança
produtiva. Antes de agir, ler nesta ordem:

1. [Indicador datado](ness-os-status.md) — estado factual e gates; prevalece
   sobre qualquer data ou SHA deste handoff.
2. [Plano master](../superpowers/plans/2026-10-12-ness-os-plano-master.md) —
   escopo F0–F8 e critérios de saída.
3. [Contexto canônico](../PROJECT_CONTEXT.md) e
   [resumo do projeto](ness-os-project-overview-2026-10-22.md).
4. [Plano GLPI T01–T14](../superpowers/plans/2026-10-12-glpi-ness-os-complete-delivery.md),
   [ADR 0020](../adr/0020-glpi-maintenance-entity-boundary.md) e
   [plano de CI isolada](../superpowers/plans/2026-10-22-local-ci-trust-boundary.md)
   para a frente atual. Os demais planos estão indexados no master.
5. Ledger local do master em
   `/home/resper/ness.OS/.superpowers/sdd/2026-10-12-ness-os-plano-master/progress.md`
   **se existir neste host**. Não depende dele para encontrar o estado
   publicado; consultar evidências versionadas e PRs/issues antes de repetir
   operações.

## Onde trabalhar

- Remoto: `resper1965/ness.OS-v2`, privado. PR #64 (`feat/incidents-rbac-local`)
  é a branch draft de entrega; PR #81 (`no-actions-release`) é a branch draft
  de CI. Antes desta atualização documental, heads consultados em 22/10:
  #64 `c6abe40`, #81 `5051d4c`; conferir novamente após qualquer push.
- O checkout de trabalho deste handoff é `/home/resper/ness.OS-clean`; o
  caminho histórico `/home/resper/ness.OS` abriga o ledger e não deve ser
  presumido como o checkout da branch ativa. Conferir `git status`, remoto,
  branch e SHA antes de editar. Preservar arquivos ignorados do usuário.
- PR #42 e issues #67, #68 e #80 foram encerrados como substituídos/organizados;
  não seguir suas instruções antigas de cobrança, grant GHCR ou revisor extra.
  [Triagem do repositório](repository-hygiene-2026-10-22.md).

## Estado que não pode ser inferido de CI verde

- Os quatro checks (`build-and-test`, `test-and-lint`, `lint`, `gitleaks`)
  passaram no SHA `5051d4c` do PR #81 durante uma janela temporária pública.
  O repositório voltou a **PRIVATE** e Actions está **desativado**. A proteção
  da `main` ainda exige esses quatro nomes do app Actions `15368`, com
  `strict=true`, administradores cobertos, zero aprovações obrigatórias por
  decisão do único desenvolvedor e force-push desativado. Isso não aprova
  automaticamente novos SHAs nem libera merge/deploy.
- O publicador local já publicou API/frontend em pacotes GHCR privados e os
  puxou por digest; nenhum deploy decorreu disso. O runner candidato executou
  backend/frontend/lint/scan em sandbox. O signer/emissor confiável não foi
  integrado: App `ness-os-local-ci` (ID 5307771) ainda precisa de permissão
  mínima de leitura de PR com readback, domínio separado do builder, falhas
  negativas ponta a ponta e revogação da primeira chave. Não emitir checks
  nem alterar a proteção por essas provas parciais. Ver runbook do PR #81
  `infra/docs/github-app-local-ci.md` e issue #69.
- A conta GLPI de manutenção 106 está **desativada**. O laboratório válido
  reproduziu seleção/leitura de entidade descendente apesar do grant não
  recursivo. Guard no Hub e bloqueio da API pública não fecham a rota direta.
  Gateway/Compose são candidatos não implantados. Não reativar 106, criar os
  três ativos nem fazer replay antes de isolamento direto comprovado. Ver
  issue #74, ADR 0020 e [execução GLPI](glpi-next-delivery-2026-10-12.md).
- Zabbix: último estado registrado é origem única coletora e destino
  mascarado. A janela terminou em 15/10/2026 11:47:35 BRT e o token anterior
  expirou. Novo corte exige janela, gates, freeze, GO e rollback; não alterar
  DNS nem permitir dupla coleta.
- Restore externo isolado pós-rotação terminou com exit 0 e PASS para o mesmo
  conjunto já registrado. Não repetir sem mudança relevante. Histórico de
  heads/tags foi sanitizado, mas refs de PR/caches remotos continuam risco
  na issue #82; não considerar a privatização como apagamento da exposição.

## Próxima execução, uma frente por vez

1. Confirmar o indicador, o checkout limpo e o estado remoto. Selecionar
   **GLPI T03** como frente principal. Usar o ADR e os testes existentes para
   preparar a matriz negativa de rota direta em isolamento; não tocar 106.
2. Se T03 depender da promoção de código, seguir o plano de CI isolada no PR
   #81 até o ponto que não exige novo host/decisão humana. A prova atual de
   WSL mostrou que `nobody` pode invocar `wsl.exe -u root`; usuários Linux ou
   Docker rootless nessa distro não isolam a chave do builder.
3. Quando T03 não puder progredir, escolher **uma** tarefa GLPI independente
   do plano T01–T14 (por exemplo, classificação read-only, teste local ou
   preparação de aceite nominal). Não repetir backups, restores, importações
   ou testes já aprovados sem alteração pertinente.
4. Para cada mudança: problema, arquivo/contrato, teste ou readback que falha
   antes e passa depois, rollback, evidência sanitizada, commit e push.
   Atualizar o indicador só se entrega, gate, bloqueio, foco ou prazo mudar.

Nenhum SLA/tenant deve ser inventado; SQL de configuração não contorna
permissão. Mudanças produtivas exigem identidade autorizada, ticket, janela,
estado anterior e retorno. O próximo desenvolvedor não deve declarar G0–G5
PASS a partir de documentação ou teste isolado.
