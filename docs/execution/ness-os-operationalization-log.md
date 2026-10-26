# Log de operacionalização ness.OS

Registro de execução por fase conforme o plano mestre. Os eventos não alteram
gates nem autorizam promoção sem evidência e decisão explícitas.

## Fase 0 — retomada da recuperação e baseline de release

- **Registro:** 2026-09-26 19:07:32 UTC (16:07:32 BRT).
- **Executor:** Codex em colaboração com resper; janela de sábado autorizada pelo
  usuário.
- **Escopo desta retomada:** verificações locais e SSH somente leitura na AIOps;
  restore do snapshot Restic em diretório temporário isolado. Nenhum serviço,
  configuração, credencial ou dado ativo foi alterado.
- **Release de referência:** commit local `3c8bb4d`; não publicado, etiquetado ou
  implantado.
- **Rollback:** não aplicável a produção porque nenhuma mudança de produção foi
  feita. O diretório temporário do restore foi removido e sua ausência foi
  confirmada. O commit é local e pode ser revertido por Git se a revisão exigir.
- **Resultado:** backup local AIOps `20260925T230000-0300`, checksums e snapshot
  externo `d66d36f3` restaurado/verificado; evidência em
  [`phase-0-aiops-recovery-2026-09-26.md`](evidence/phase-0-aiops-recovery-2026-09-26.md).
  Gate geral continua **FAIL** por falta de hashes/digests atuais, ensaio de
  rollback associado a release, CI em runner limpo e validações atuais de
  Zabbix/UAT.

## Fase 0 — reconciliação somente leitura do backend AIOps

- **Registro:** 2026-09-26 19:29 UTC (16:29 BRT).
- **Executor:** Codex em colaboração com resper; janela de sábado autorizada.
- **Escopo:** SHA-256 remoto/local de `app/backend/app` e inspeção de imagem dos
  17 containers ativos na AIOps; somente leitura.
- **Release de referência:** worktree local em `04b432d`, não publicado nem
  implantado.
- **Rollback:** não aplicável; nenhuma alteração remota foi feita.
- **Resultado:** 36 hashes iguais, 39 diferentes e 2 arquivos somente locais
  na árvore Python. Quatro imagens próprias não têm `RepoDigests`; 13 imagens
  externas têm digest observado no `Config.Image`. Isso renova apenas parte da
  reconciliação; não associa o runtime a um commit/release nem prova rollback.
  O Compose que iniciou `ninf-api` também difere do arquivo local.
  Evidência em
  [`phase-0-aiops-code-hash-2026-09-26.md`](evidence/phase-0-aiops-code-hash-2026-09-26.md).
  Gate permanece **FAIL**.
- Às 19:33 UTC, um probe Contabo somente leitura usou `client_credentials` e
  retornou HTTP 401. A revisão posterior do cliente versionado confirmou que o
  grant esperado é `password`; `CONTABO_USERNAME` e `CONTABO_PASSWORD` estão
  ausentes do container AIOps, então o probe não valida credenciais completas.
  Nenhuma listagem de VPS ocorreu. Corrigido em
  [`phase-0-aiops-code-hash-2026-09-26.md`](evidence/phase-0-aiops-code-hash-2026-09-26.md).
- Às 19:36 UTC, a revisão de permissões encontrou o backup antigo
  `.env.pre-gate0-20260820T163730-0300` como `0644`, com valores não vazios de
  Client ID/Secret Contabo e sem referência por nome em systemd ou arquivos da
  aplicação. O modo foi restringido a `0600` e verificado por `stat`; nenhum
  conteúdo ou serviço mudou e não houve restart. Evidência na seção Contabo de
  [`phase-0-aiops-code-hash-2026-09-26.md`](evidence/phase-0-aiops-code-hash-2026-09-26.md).
- Às 19:40 UTC, revalidei no AIOps o conjunto `20260925T230000-0300` (marcador
  presente, 24/24 checksums aprovados, idade 17h36), resultados dos serviços e
  timers locais/externos. Nenhum backup foi disparado manualmente. Evidência em
  [`phase-0-aiops-recovery-2026-09-26.md`](evidence/phase-0-aiops-recovery-2026-09-26.md).
