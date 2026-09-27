# Phase 0 Recovery and Release Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restabelecer backups e restaurações confiáveis do Hub e do Zabbix e criar uma release reproduzível antes de mudanças funcionais em produção.

**Architecture:** Os jobs systemd chamam scripts idempotentes que produzem conjuntos locais completos, enviam snapshots criptografados ao Object Storage e verificam restauração isolada. Um manifesto associa a release local aos artefatos realmente executados em produção.

**Tech Stack:** Bash, systemd, Docker Compose, Restic, S3 compatível da Contabo, Git, Python e pytest.

**Spec:** `docs/architecture/ness-os-official-architecture.md` e `docs/evaluations/ness-os-system-review-2026-09-17.md`.

## Global Constraints

- Executar correções de backup antes de mudanças funcionais em produção; desenvolvimento e testes locais das demais fases podem avançar enquanto o gate está pendente.
- Validar caminhos resolvidos antes de qualquer limpeza; não apagar conjuntos até a nova restauração passar.
- Separar os repositórios Restic do Hub, Zabbix, Psono e futuro Wazuh.
- Registrar apenas presença e fingerprint de segredos, nunca seus valores.

---

### Task 1: Reproduzir e corrigir a falha do backup do Hub

**Files:**
- Modify: `infra/scripts/aiops-nightly-backup.sh`
- Modify: `infra/scripts/aiops-deployment-backup.sh`
- Test: `infra/tests/test-aiops-nightly-backup.sh`
- Test: `infra/tests/test-aiops-runtime-preflight.sh`

**Interfaces:** `aiops-nightly-backup.sh` deve concluir sem depender da existência da bridge `docker0`; deve emitir marcador `COMPLETED` somente depois de validar todos os artefatos obrigatórios.

- [x] Criar teste que execute o caminho de descoberta do Compose com uma inspeção Docker simulando `docker0` ausente e confirmar falha atual.
- [x] Executar `bash infra/tests/test-aiops-nightly-backup.sh`; esperado: falha no novo caso antes da correção.
- [x] Separar coleta por `docker compose exec` de qualquer criação de container auxiliar e validar previamente a rede escolhida pelo projeto.
- [x] Fazer o script abortar antes de `COMPLETED` quando dump, manifesto ou checksum estiver ausente ou vazio.
- [x] Executar `bash infra/tests/test-aiops-nightly-backup.sh && bash infra/tests/test-aiops-runtime-preflight.sh`; esperado: todos os casos aprovados.
- [x] Em produção, executar `systemctl start ness-aiops-backup.service` e confirmar `ActiveState=inactive`, `Result=success` e um novo conjunto com `COMPLETED` no mesmo dia.
- [x] Commit: `git add infra/scripts/aiops-nightly-backup.sh infra/scripts/aiops-deployment-backup.sh infra/tests/test-aiops-nightly-backup.sh infra/tests/test-aiops-runtime-preflight.sh && git commit -m "fix(backup): make Hub backup independent of docker0"`.

### Task 2: Validar cópia externa e restauração do Hub

**Files:**
- Modify: `infra/scripts/aiops-deployment-remote-verify.sh`
- Modify: `infra/scripts/aiops-isolated-restore-test.sh`
- Test: `infra/tests/test-object-storage-restic-tooling.sh`
- Create: `docs/execution/evidence/phase-0-hub-recovery.md`

**Interfaces:** A verificação remota deve selecionar o snapshot correspondente ao novo conjunto completo, não reutilizar silenciosamente o último snapshot válido.

- [x] Criar teste com conjunto local mais recente que o snapshot remoto e exigir saída não zero.
- [x] Executar `bash infra/tests/test-object-storage-restic-tooling.sh`; esperado: novo caso falha antes da correção.
- [x] Comparar `backup_set_id` do manifesto local com tags do snapshot Restic e falhar em divergência.
- [x] Executar novamente o teste; esperado: aprovado.
- [x] Iniciar `ness-aiops-object-storage-backup.service`, executar `aiops-deployment-remote-verify.sh` e confirmar o mesmo `backup_set_id` local e remoto.
- [x] Executar `aiops-isolated-restore-test.sh` usando o snapshot remoto mais recente; esperado: bancos e configurações restaurados em ambiente isolado e sondas de integridade aprovadas.
- [x] Registrar em `phase-0-hub-recovery.md` horários UTC, IDs, checksums, duração e resultado sem segredos.
- [x] Commit: `git add infra/scripts/aiops-deployment-remote-verify.sh infra/scripts/aiops-isolated-restore-test.sh infra/tests/test-object-storage-restic-tooling.sh docs/execution/evidence/phase-0-hub-recovery.md && git commit -m "test(recovery): prove current Hub offsite restore"`.

### Task 3: Reativar proteção do Zabbix

**Files:**
- Modify: `infra/scripts/zabbix-nightly-backup.sh`
- Modify: `infra/scripts/zabbix-isolated-restore-test.sh`
- Modify: `infra/scripts/verify-zabbix-restic-restore.sh`
- Modify: `infra/systemd/ness-zabbix-backup.timer`
- Modify: `infra/systemd/ness-zabbix-object-storage-backup.timer`
- Test: `infra/tests/test-zabbix-upgrade-safety.sh`
- Create: `docs/execution/evidence/phase-0-zabbix-recovery.md`

**Interfaces:** Backup diário local e externo com RPO máximo de 24 horas; restauração usa versão compatível com Zabbix 7.0.27 e MariaDB em produção.

- [x] Acrescentar teste de manifesto completo, checksum, versão do banco e rejeição de conjunto parcial.
- [x] Executar `bash infra/tests/test-zabbix-upgrade-safety.sh`; esperado: falha nos requisitos ainda ausentes.
- [x] Implementar os campos e validações mínimos e repetir o teste; esperado: aprovado.
- [x] Instalar as units versionadas, executar `systemctl daemon-reload` e habilitar os dois timers com `systemctl enable --now`; ambos estão habilitados e ativos.
- [x] Disparar backup local e externo; cópia externa, `restic check` e associação ao conjunto local atual aprovados. A próxima execução ainda deve comprovar reutilização incremental do parent.
- [x] Restaurar o snapshot em instância isolada e verificar versão e contagens: Zabbix 7.0.27, MariaDB 10.11.18, 203 tabelas, 685 hosts, 64.226 itens, 26.697 triggers e 362 templates. A leitura autenticada da API confirmou 260 hosts; `template.get` não é permitido ao usuário técnico e permanece blocker para a onda funcional.
- [x] Registrar evidência e a próxima execução de cada timer, incluindo os blockers atuais.
- [x] Commit: `git add infra/scripts/zabbix-nightly-backup.sh infra/scripts/zabbix-isolated-restore-test.sh infra/scripts/verify-zabbix-restic-restore.sh infra/systemd/ness-zabbix-backup.timer infra/systemd/ness-zabbix-object-storage-backup.timer infra/tests/test-zabbix-upgrade-safety.sh docs/execution/evidence/phase-0-zabbix-recovery.md && git commit -m "fix(recovery): restore Zabbix backup schedule"`.

### Task 4: Criar o manifesto de release e reconciliar a árvore

**Files:**
- Create: `infra/scripts/ness-release-manifest.py`
- Create: `infra/tests/test-ness-release-manifest.py`
- Create: `docs/runbooks/release-and-rollback.md`
- Create: `docs/execution/evidence/phase-0-release-baseline.md`

**Interfaces:** `python infra/scripts/ness-release-manifest.py --output <path>` produz JSON com `git_commit`, `git_dirty`, imagens e digests, hashes dos arquivos implantados, versões e nomes de units; valores secretos são substituídos por presença booleana.

- [x] Escrever testes para repositório limpo/sujo, digest ausente, arquivo divergente, filtragem de chaves sensíveis e descoberta de Compose sem varrer dependências/builds.
- [x] Executar `python -m pytest infra/tests/test-ness-release-manifest.py -q`; falha inicial observada antes da implementação.
- [x] Implementar o gerador determinístico; sete testes aprovados após a regressão de varredura.
- [ ] Agrupar todas as mudanças locais por domínio, testar cada grupo e criar commits revisáveis sem usar `git add -A`. Os grupos de código verificados estão commitados, incluindo `3c8bb4d` (n8n/readiness); não há mudanças pendentes sob `app/` ou `infra/`. Snapshot do worktree em 26/09 às 19:22 UTC: 6 arquivos rastreados modificados e 40 não rastreados (documentos/evidências e `.codex-tmp-*`); classificar e revisar individualmente antes de consolidar, preservando-os.
- [ ] Manifesto local gerado para o commit de código `3c8bb4d` e validado com 9 testes; comparar novamente após renovar os fatos de produção. A coleta remota de hashes/digests ainda é de 25/09 e registra 126 arquivos montados/instalados, 8/19 imagens sem digest, 43 divergências e 47 paths sem hash remoto. Release continua bloqueada.
- [x] Documentar deploy por digest, migração, sonda, rollback e restauração no runbook.
- [ ] Criar tag de release somente depois de `git status --short` vazio e dos checks de CI aprovados.
- [x] Commits do manifesto/runbook/evidência: `b5bd4c6`, `0533555`, `6f3ebd7`.

### Task 5: Aprovar o gate da Fase 0

**Files:**
- Create: `docs/execution/gates/phase-0-recovery-release.md`

- [x] Confirmar backup completo do Hub e Zabbix com idade inferior a 24 horas.
- [x] Confirmar snapshots externos correspondentes aos conjuntos locais atuais (Hub e Zabbix PASS).
- [x] Confirmar restaurações isoladas do Hub, Zabbix e Psono.
- [x] Confirmar timers habilitados, última execução bem-sucedida e próxima execução agendada.
- [ ] Confirmar produção associada a commit e digests imutáveis, com rollback ensaiado.
- [x] Executar `git diff --check` e os testes alterados nesta fase; saída limpa e código zero.
- [x] Registrar `PASS` ou `FAIL` por critério. Gate geral permanece `FAIL`; mudanças dependentes não foram iniciadas.
- [x] Commit de gate: `71b6ed9` (atualizações de evidência nos commits `9772e14`, `c2ab106` e `e48b176`).
