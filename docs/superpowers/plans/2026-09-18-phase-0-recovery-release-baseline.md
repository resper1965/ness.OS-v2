# Phase 0 Recovery and Release Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restabelecer backups e restaurações confiáveis do Hub e do Zabbix e criar uma release reproduzível antes de mudanças funcionais.

**Architecture:** Os jobs systemd chamam scripts idempotentes que produzem conjuntos locais completos, enviam snapshots criptografados ao Object Storage e verificam restauração isolada. Um manifesto associa a release local aos artefatos realmente executados em produção.

**Tech Stack:** Bash, systemd, Docker Compose, Restic, S3 compatível da Contabo, Git, Python e pytest.

**Spec:** `docs/architecture/ness-os-official-architecture.md` e `docs/evaluations/ness-os-system-review-2026-09-17.md`.

## Global Constraints

- Executar correções de backup antes das demais fases.
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

- [ ] Criar teste que execute o caminho de descoberta do Compose com uma inspeção Docker simulando `docker0` ausente e confirmar falha atual.
- [ ] Executar `bash infra/tests/test-aiops-nightly-backup.sh`; esperado: falha no novo caso antes da correção.
- [ ] Separar coleta por `docker compose exec` de qualquer criação de container auxiliar e validar previamente a rede escolhida pelo projeto.
- [ ] Fazer o script abortar antes de `COMPLETED` quando dump, manifesto ou checksum estiver ausente ou vazio.
- [ ] Executar `bash infra/tests/test-aiops-nightly-backup.sh && bash infra/tests/test-aiops-runtime-preflight.sh`; esperado: todos os casos aprovados.
- [ ] Em produção, executar `systemctl start ness-aiops-backup.service` e confirmar `ActiveState=inactive`, `Result=success` e um novo conjunto com `COMPLETED` no mesmo dia.
- [ ] Commit: `git add infra/scripts/aiops-nightly-backup.sh infra/scripts/aiops-deployment-backup.sh infra/tests/test-aiops-nightly-backup.sh infra/tests/test-aiops-runtime-preflight.sh && git commit -m "fix(backup): make Hub backup independent of docker0"`.

### Task 2: Validar cópia externa e restauração do Hub

**Files:**
- Modify: `infra/scripts/aiops-deployment-remote-verify.sh`
- Modify: `infra/scripts/aiops-isolated-restore-test.sh`
- Test: `infra/tests/test-object-storage-restic-tooling.sh`
- Create: `docs/execution/evidence/phase-0-hub-recovery.md`

**Interfaces:** A verificação remota deve selecionar o snapshot correspondente ao novo conjunto completo, não reutilizar silenciosamente o último snapshot válido.

- [ ] Criar teste com conjunto local mais recente que o snapshot remoto e exigir saída não zero.
- [ ] Executar `bash infra/tests/test-object-storage-restic-tooling.sh`; esperado: novo caso falha antes da correção.
- [ ] Comparar `backup_set_id` do manifesto local com tags do snapshot Restic e falhar em divergência.
- [ ] Executar novamente o teste; esperado: aprovado.
- [ ] Iniciar `ness-aiops-object-storage-backup.service`, executar `aiops-deployment-remote-verify.sh` e confirmar o mesmo `backup_set_id` local e remoto.
- [ ] Executar `aiops-isolated-restore-test.sh` usando o snapshot remoto mais recente; esperado: bancos e configurações restaurados em ambiente isolado e sondas de integridade aprovadas.
- [ ] Registrar em `phase-0-hub-recovery.md` horários UTC, IDs, checksums, duração e resultado sem segredos.
- [ ] Commit: `git add infra/scripts/aiops-deployment-remote-verify.sh infra/scripts/aiops-isolated-restore-test.sh infra/tests/test-object-storage-restic-tooling.sh docs/execution/evidence/phase-0-hub-recovery.md && git commit -m "test(recovery): prove current Hub offsite restore"`.

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

- [ ] Acrescentar teste de manifesto completo, checksum, versão do banco e rejeição de conjunto parcial.
- [ ] Executar `bash infra/tests/test-zabbix-upgrade-safety.sh`; esperado: falha nos requisitos ainda ausentes.
- [ ] Implementar os campos e validações mínimos e repetir o teste; esperado: aprovado.
- [ ] Instalar as units versionadas, executar `systemctl daemon-reload` e habilitar os dois timers com `systemctl enable --now`.
- [ ] Disparar backup local e externo; confirmar snapshot do dia, checksum e ausência de segredos no log.
- [ ] Restaurar o snapshot em instância isolada e verificar versão, contagens de hosts/templates e login técnico somente leitura.
- [ ] Registrar evidência e a próxima execução de cada timer.
- [ ] Commit: `git add infra/scripts/zabbix-nightly-backup.sh infra/scripts/zabbix-isolated-restore-test.sh infra/scripts/verify-zabbix-restic-restore.sh infra/systemd/ness-zabbix-backup.timer infra/systemd/ness-zabbix-object-storage-backup.timer infra/tests/test-zabbix-upgrade-safety.sh docs/execution/evidence/phase-0-zabbix-recovery.md && git commit -m "fix(recovery): restore Zabbix backup schedule"`.

### Task 4: Criar o manifesto de release e reconciliar a árvore

**Files:**
- Create: `infra/scripts/ness-release-manifest.py`
- Create: `infra/tests/test-ness-release-manifest.py`
- Create: `docs/runbooks/release-and-rollback.md`
- Create: `docs/execution/evidence/phase-0-release-baseline.md`

**Interfaces:** `python infra/scripts/ness-release-manifest.py --output <path>` produz JSON com `git_commit`, `git_dirty`, imagens e digests, hashes dos arquivos implantados, versões e nomes de units; valores secretos são substituídos por presença booleana.

- [ ] Escrever testes para repositório limpo/sujo, digest ausente, arquivo divergente e filtragem de chaves sensíveis.
- [ ] Executar `python -m pytest infra/tests/test-ness-release-manifest.py -q`; esperado: falha inicial.
- [ ] Implementar o gerador determinístico e repetir; esperado: todos os testes aprovados.
- [ ] Agrupar as mudanças locais existentes por domínio, executar os testes próprios de cada grupo e criar commits revisáveis sem usar `git add -A`.
- [ ] Gerar manifesto local e manifesto de produção; resolver toda divergência de arquivo executável ou imagem antes de marcar a release.
- [ ] Documentar deploy por digest, migração, sonda, rollback e restauração no runbook.
- [ ] Criar tag de release somente depois de `git status --short` vazio e dos checks de CI aprovados.
- [ ] Commit: `git add infra/scripts/ness-release-manifest.py infra/tests/test-ness-release-manifest.py docs/runbooks/release-and-rollback.md docs/execution/evidence/phase-0-release-baseline.md && git commit -m "feat(release): add reproducible production manifest"`.

### Task 5: Aprovar o gate da Fase 0

**Files:**
- Create: `docs/execution/gates/phase-0-recovery-release.md`

- [ ] Confirmar backup completo do Hub e Zabbix com idade inferior a 24 horas.
- [ ] Confirmar snapshots externos correspondentes aos conjuntos locais atuais.
- [ ] Confirmar restaurações isoladas do Hub, Zabbix e Psono.
- [ ] Confirmar timers habilitados, última execução bem-sucedida e próxima execução agendada.
- [ ] Confirmar produção associada a commit e digests imutáveis, com rollback ensaiado.
- [ ] Executar `git diff --check` e os testes alterados nesta fase; esperado: saída limpa e código zero.
- [ ] Registrar `PASS` ou `FAIL` por critério. Não iniciar mudanças dependentes com qualquer `FAIL`.
- [ ] Commit: `git add docs/execution/gates/phase-0-recovery-release.md && git commit -m "docs(gate): approve recovery and release baseline"`.
