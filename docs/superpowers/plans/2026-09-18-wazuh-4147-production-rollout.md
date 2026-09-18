# Wazuh 4.14.7 Production Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a reproducible, recoverable single-node Wazuh 4.14.7 deployment and controlled 5→25→50 endpoint production rollout.

**Architecture:** One dedicated VPS runs the official Wazuh 4.14.7 single-node Docker stack behind restricted network access. Repository checks validate version pinning, firewall exposure, secrets, backup/restore and wave gates before any external deployment.

**Tech Stack:** Ansible, Docker Compose, UFW, Wazuh 4.14.7, Bash test scripts, Restic/S3-compatible object storage.

**Spec:** `docs/superpowers/specs/2026-09-18-wazuh-production-entry-design.md`

## Global Constraints

- Wazuh production baseline is exactly `4.14.7`.
- Wave 1 uses one dedicated, freshly installed VPS.
- Indexer port 9200 is never public.
- Agent enrollment and traffic are limited to approved source networks.
- Observation mode is enabled for the first 48 hours.
- Zabbix services and agents are outside the Wazuh rollback boundary.
- No infrastructure purchase or deployment occurs without an explicit target host and credentials supplied outside Git.

---

### Task 1: Make the single-node playbook safe and parameterized

**Files:**
- Modify: `infra/ansible/playbooks/wazuh-hub.yml`
- Create: `infra/ansible/inventory/group_vars/wazuh_hubs.example.yml`
- Create: `infra/tests/test-wazuh-playbook-safety.sh`

**Interfaces:**
- Consumes: `wazuh_version`, approved agent CIDRs, admin CIDRs and external secret paths.
- Produces: idempotent Wazuh 4.14.7 single-node installation.

- [ ] **Step 1: Write a static safety test**

The script must fail unless the playbook pins `4.14.7`, omits public 9200,
requires non-default CIDRs, avoids `git force: yes`, marks secret files
`no_log: true`, and uses the Docker Compose plugin.

- [ ] **Step 2: Run the test and verify current failure**

Run: `bash infra/tests/test-wazuh-playbook-safety.sh`

Expected: failure for version 4.14.6, broad VLAN default, exposed 9200 and forced Git update.

- [ ] **Step 3: Refactor the playbook**

Pin `4.14.7`; assert that agent/admin CIDR lists are non-empty and do not
contain `0.0.0.0/0`; remove HTTP, public indexer and default Syslog exposure;
allow dashboard/API only from admin CIDRs; clone the exact tag without forced
replacement; validate existing checkout state; keep generated certificates and
credentials in inventory-supplied external paths.

- [ ] **Step 4: Run syntax and safety checks**

Run: `ansible-playbook --syntax-check -i infra/ansible/inventory/hosts.yml infra/ansible/playbooks/wazuh-hub.yml && bash infra/tests/test-wazuh-playbook-safety.sh`

Expected: both commands exit zero.

- [ ] **Step 5: Commit the safe deployment baseline**

```bash
git add infra/ansible/playbooks/wazuh-hub.yml infra/ansible/inventory/group_vars/wazuh_hubs.example.yml infra/tests/test-wazuh-playbook-safety.sh
git commit -m "fix: harden Wazuh 4.14.7 single-node deployment"
```

### Task 2: Add deployment preflight and readiness evidence

**Files:**
- Create: `infra/scripts/wazuh-production-preflight.sh`
- Create: `infra/tests/test-wazuh-production-preflight.sh`
- Create: `docs/runbooks/wazuh-wave1-readiness.md`

**Interfaces:**
- Consumes: target inventory, secret-file locations and approved CIDRs.
- Produces: machine-readable PASS/FAIL evidence without changing the target.

- [ ] **Step 1: Write fixture-based preflight tests**

Test failures for missing secrets, insufficient disk, public 9200, absent NTP,
Docker unavailable and missing backup destination; test one complete passing
fixture.

- [ ] **Step 2: Run tests and confirm the script is absent**

Run: `bash infra/tests/test-wazuh-production-preflight.sh`

Expected: failure because the preflight script does not exist.

- [ ] **Step 3: Implement read-only checks**

The script must check CPU, memory, free disk, NTP, Docker/Compose, listening
ports, UFW policy, DNS/TLS inputs, secret file permissions, backup endpoint and
clock skew. Emit one JSON object with individual checks and a final status; do
not print secret contents.

- [ ] **Step 4: Run fixture tests and ShellCheck**

Run: `bash infra/tests/test-wazuh-production-preflight.sh && shellcheck infra/scripts/wazuh-production-preflight.sh`

Expected: all fixture cases pass and ShellCheck reports no errors.

- [ ] **Step 5: Commit readiness tooling**

```bash
git add infra/scripts/wazuh-production-preflight.sh infra/tests/test-wazuh-production-preflight.sh docs/runbooks/wazuh-wave1-readiness.md
git commit -m "feat: add Wazuh production readiness gate"
```

### Task 3: Add backup and isolated restore verification

**Files:**
- Create: `infra/scripts/wazuh-backup.sh`
- Create: `infra/scripts/wazuh-isolated-restore-test.sh`
- Create: `infra/tests/test-wazuh-backup-tooling.sh`
- Create: `docs/runbooks/wazuh-backup-restore.md`

**Interfaces:**
- Consumes: Wazuh configuration, certificates, indexer snapshot, Restic repository and S3 credentials from environment files.
- Produces: encrypted snapshot, SHA-256 manifest, `COMPLETED` marker and isolated restore evidence.

- [ ] **Step 1: Write static and fixture tests**

Require strict shell mode, explicit source allowlist, private temporary
directory, Restic `check`, manifest verification, cleanup trap and refusal to
restore over the live Wazuh directory.

- [ ] **Step 2: Run tests and confirm failure**

Run: `bash infra/tests/test-wazuh-backup-tooling.sh`

Expected: failure because backup scripts are absent.

- [ ] **Step 3: Implement backup and isolated restore scripts**

Back up configuration, external certificates and an indexer snapshot reference;
write hashes before upload; verify the Restic repository; restore into a newly
created temporary directory; compare every manifest entry; emit dated evidence;
never stop or overwrite the live stack.

- [ ] **Step 4: Run tests and ShellCheck**

Run: `bash infra/tests/test-wazuh-backup-tooling.sh && shellcheck infra/scripts/wazuh-backup.sh infra/scripts/wazuh-isolated-restore-test.sh`

Expected: all checks pass.

- [ ] **Step 5: Commit recovery tooling**

```bash
git add infra/scripts/wazuh-backup.sh infra/scripts/wazuh-isolated-restore-test.sh infra/tests/test-wazuh-backup-tooling.sh docs/runbooks/wazuh-backup-restore.md
git commit -m "feat: verify Wazuh backup and isolated restore"
```

### Task 4: Define and automate wave gates

**Files:**
- Create: `infra/scripts/wazuh-wave-gate.py`
- Create: `infra/tests/test-wazuh-wave-gate.py`
- Create: `docs/runbooks/wazuh-production-rollout.md`

**Interfaces:**
- Consumes: JSON measurements for agent connectivity, tenant isolation, queue failures, duplicates, endpoint overhead, backup and restore.
- Produces: deterministic `GO`, `HOLD` or `ROLLBACK` decision and failed criteria.

- [ ] **Step 1: Write decision-table tests**

```python
def test_cross_tenant_event_forces_rollback():
    result = evaluate(metrics(cross_tenant_events=1))
    assert result.decision == "ROLLBACK"


def test_missing_restore_holds_wave():
    result = evaluate(metrics(restore_verified=False))
    assert result.decision == "HOLD"


def test_healthy_measurements_allow_expansion():
    result = evaluate(metrics())
    assert result.decision == "GO"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest -q infra/tests/test-wazuh-wave-gate.py`

Expected: module import fails.

- [ ] **Step 3: Implement explicit gates**

`ROLLBACK` on any cross-tenant event, security-critical data loss or sustained
material Zabbix regression. `HOLD` on connectivity below 98%, duplicate rate
above 1%, unprocessed signals, missing backup/restore, missing owner/runbook or
insufficient observation time. `GO` only when every mandatory criterion passes.
The rollout runbook documents 5 endpoints/48 hours, 25 endpoints/7 days and the
50-endpoint Wave 1 acceptance.

- [ ] **Step 4: Run rollout checks**

Run: `pytest -q infra/tests/test-wazuh-wave-gate.py && python infra/scripts/wazuh-wave-gate.py --input infra/tests/fixtures/wazuh-wave-healthy.json`

Expected: tests pass and the fixture returns `GO` with exit code zero.

- [ ] **Step 5: Commit wave controls**

```bash
git add infra/scripts/wazuh-wave-gate.py infra/tests/test-wazuh-wave-gate.py infra/tests/fixtures/wazuh-wave-healthy.json docs/runbooks/wazuh-production-rollout.md
git commit -m "feat: gate Wazuh production rollout by evidence"
```

### Task 5: Verify repository readiness and record the external deployment gate

**Files:**
- Create: `docs/execution/wazuh-wave1-readiness-2026-09-18.md`

**Interfaces:**
- Consumes: outputs from Tasks 1–4 and the application ingestion plan.
- Produces: dated readiness record identifying repository-complete work and external inputs required for deployment.

- [ ] **Step 1: Run all Wazuh repository checks**

Run: `bash infra/tests/test-wazuh-playbook-safety.sh && bash infra/tests/test-wazuh-production-preflight.sh && bash infra/tests/test-wazuh-backup-tooling.sh && pytest -q infra/tests/test-wazuh-wave-gate.py`

Expected: every command exits zero.

- [ ] **Step 2: Run existing infrastructure regressions**

Run: `for test_file in infra/tests/test-*.sh; do bash "$test_file"; done && pytest -q infra/tests/test-hub-health-history.py`

Expected: all existing infrastructure checks pass.

- [ ] **Step 3: Record the deployment gate**

Document exact evidence hashes, remaining external inputs (dedicated VPS IP,
approved CIDRs, DNS name, secret paths, S3 bucket and selected endpoint IDs),
the observation-mode default and the first allowed command. Do not record
credentials or claim that a live deployment occurred.

- [ ] **Step 4: Commit readiness evidence**

```bash
git add docs/execution/wazuh-wave1-readiness-2026-09-18.md
git commit -m "docs: record Wazuh wave one deployment gate"
```

