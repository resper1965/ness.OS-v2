# Log de operacionalização ness.OS

Registro de execução por fase conforme o plano mestre. Os eventos não alteram
gates nem autorizam promoção sem evidência e decisão explícitas.

## Fase 0 — retomada da recuperação e baseline de release

- **Registro:** 2026-09-27 15:31–15:32 UTC (12:31–12:32 BRT).
- **Escopo:** validação do backup AIOps mais recente, checksums, resultado dos
  timers, identidade do verificador remoto, restore Restic isolado e limpeza do
  temporário. Nenhum serviço ou dado ativo foi alterado.
- **Resultado:** conjunto `20260926T230011-0300` passou seus checksums; serviços
  local e externo concluíram com código 0. Snapshot Restic
  `4ca602426be75a75ebe7b44210e08ffb2ed1f7417e586efe302361ad1d23f482` restaurou
  862,761 MiB, verificou 26 arquivos e o diretório temporário foi removido.
  Evidência em
  [`phase-0-aiops-recovery-2026-09-27.md`](evidence/phase-0-aiops-recovery-2026-09-27.md).
- **Limite:** Zabbix atual não foi validado; backup, snapshot externo e timer
  seguem sem evidência recente. Gate 0 continua **FAIL**.

- **Registro:** 2026-09-27 15:29–15:39 UTC (12:29–12:39 BRT).
- **Escopo:** OAuth Contabo e consultas `GET /v1/compute/instances` e
  `GET /v1/firewalls`; sonda SSH sem comando remoto efetivo para a VPS Zabbix
  canônica. A pentest foi excluída do escopo.
- **Resultado:** API autenticada agora funciona e confirma três VPS do projeto
  em execução. A política Contabo `ness` está inativa. SSH em
  `144.91.72.202:22` expira; na porta documentada `2222`, o host responde, mas
  rejeita a chave com `Permission denied (publickey)`. Nenhum comando remoto
  executado. Evidência em
  [`phase-0-contabo-readonly-2026-09-27.md`](evidence/phase-0-contabo-readonly-2026-09-27.md).
- **Limite:** nenhuma configuração foi modificada. Hashes/digests de produção,
  acesso SSH válido ao Zabbix, token de leitura e rollback da release seguem
  pendentes; Gate 0 continua **FAIL**.

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
