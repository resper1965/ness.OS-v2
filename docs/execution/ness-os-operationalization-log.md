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
