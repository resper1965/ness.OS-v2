# ness.OS MVP Delivery and Post-MVP Evolution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this delivery plan task-by-task. Follow each referenced phase plan for its exact code edits, TDD steps, commands, and commits.

**Goal:** Deliver and accept a usable ness.OS AIOps MVP for the Zabbix-to-Hub-to-GLPI operator workflow, then onboard Wazuh as a post-MVP security source.

**Architecture:** Execute existing phase plans as the detailed implementation source. The MVP covers identity/tenant boundaries, trustworthy Zabbix and GLPI contracts, durable incident handling, runtime health and operator UI. Keep local implementation/test work distinct from production rollout; Fase 0 remains a hard production gate. Wazuh stays outside MVP and uses its existing dedicated rollout and ingestion plans after MVP acceptance and cost/capacity approval.

**Tech Stack:** FastAPI, React/Vite, PostgreSQL, Redis/Celery, Authentik/OIDC, Zabbix 7.0, GLPI, Docker Compose, pytest, Ruff, Bash, Restic/S3 and Wazuh 4.14.7 for post-MVP.

**Spec:** `docs/superpowers/specs/2026-09-27-ness-os-mvp-delivery-and-evolution-design.md`

## Global Constraints

- Zabbix is canonical for availability and capacity; GLPI is canonical for assets and tickets; Authentik provides operator identity.
- Backend authorization resolves effective role and tenant; client-supplied tenant is never authority.
- Every operational value exposes source, last valid collection, freshness and error; a failed collection never appears healthy.
- Duplicate delivery and retries never create duplicate incidents or tickets.
- The Contabo API stays read-only in MVP; no automatic remediation ships in MVP.
- Wazuh production deployment is post-MVP; prepare without purchase before its approved capacity/cost gate.
- Local implementation and tests may proceed while Fase 0 is pending; production schema, auth, routing, provisioning and deploy remain blocked until Fase 0 passes.
- Preserve all existing local work. Stage only files enumerated by the phase task; never use `git add -A`.
- Use Ponytail full for code: reuse existing patterns, add no dependencies without need, keep changes minimal. Keep Caveman compression in chat only; persisted code, plans and evidence use clear standard Portuguese/English prose.

## Review Focus

- Unknown or ambiguous source-to-tenant mapping: reject the signal and expose bounded failure state; no cross-tenant fallback.
- Duplicate event, delayed retry or partial GLPI failure: preserve one incident/ticket relationship and recover without data loss.
- Stale or unavailable source/worker: retain last valid timestamp and expose source error; never report empty/healthy by default.
- User with valid login but wrong tenant or role: reject at API and streaming boundaries, not only in frontend.
- Wazuh absent during MVP: display planned/unavailable state without blocking Zabbix/GLPI workflows or fabricating security status.

---

## Execution Model

Detailed task steps remain in the referenced plans. For each phase, load `superpowers:executing-plans`, read that plan's task brief, follow its RED/GREEN test steps, compare every expected result, and commit only its enumerated files. A phase is complete only when its plan's gate task and required evidence pass. This document orders those plans and defines the MVP boundary; it does not replace their component-level steps.

## MVP Acceptance Traceability

| MVP criterion | Owning plan tasks |
|---|---|
| Zabbix signal becomes a Hub incident and linked GLPI ticket | Phase 2 Tasks 4–5; Phase 6 Tasks 2–3 |
| Duplicate delivery/retry preserves one incident and ticket | Phase 2 Task 4; Phase 3 Task 3; Phase 6 Task 3 |
| Tenant boundary holds through API and operator journeys | Phase 1 Tasks 1, 4, 6; Phase 6 Task 2 |
| Source, worker and GLPI failures expose last success and error | Phase 3 Tasks 1–2; Phase 4 Tasks 1, 3; Phase 6 Task 3 |
| State, assignment and integration actions are auditable | Phase 2 Task 4; Phase 6 Tasks 1–3 |
| Backend tests, frontend build and applicable lint pass | Phase 1–4 task gates; Phase 3 Task 5; Phase 6 Task 5 |
| Release identity, backup/restore and rollback are proved | Phase 0 Tasks 1–5; Phase 3 Task 4; Phase 6 Task 4 |
| Production acceptance requires approved release/security gates | Phase 0 Task 5; Phase 1–4 gate tasks; Phase 6 Task 5 |

### Task 1: Reconcile the phase plans with the approved MVP scope

**Files:**
- Modify: `docs/superpowers/plans/2026-09-18-ness-os-full-operationalization.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-0-recovery-release-baseline.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-1-identity-tenant-controls.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-2-zabbix-glpi-operations.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-4-dashboard-operational-truth.md`
- Modify: `docs/superpowers/plans/2026-09-18-phase-6-integrated-acceptance.md`

**Interfaces:** The master plan maps each criterion in the MVP spec to one phase task and one exit gate. Phase plans distinguish local development from production rollout. Phase 4's Wazuh cost/capacity work is a post-MVP gate and cannot block MVP acceptance.

- [x] Add a requirement-to-task table to the master plan for all eight MVP acceptance criteria.
- [x] Correct phase gate wording so local code and tests may proceed while Fase 0 is pending, with no production rollout before Fase 0 approval.
- [x] Move Wazuh production readiness out of the Phase 4 MVP exit gate; preserve capacity/cost approval as a prerequisite to Wazuh purchase and rollout.
- [x] Mark already completed Phase 3 Task 1 by its existing commit `342a817`; do not repeat its implementation.
- [x] Run `git diff --check`; no whitespace errors, and the Task 1 commit changed only the seven listed plan files.
- [x] Commit only these plan files as `4bf9c68` (`docs(plan): align phase gates with ness.OS MVP`).

### Task 2: Complete identity and tenant controls

**Plan:** `docs/superpowers/plans/2026-09-18-phase-1-identity-tenant-controls.md`

**Interfaces:** Produces approved route/role/tenant matrix, effective tenant enforcement, session revocation behavior and a Phase 1 exit gate consumed by Phase 2, Phase 4 and UAT.

- [ ] Execute Phase 1 Tasks 1–6 in order, exactly as specified in its plan.
- [ ] Run its task-level tests before each commit and its gate command: `python -m pytest app/backend/tests/test_authentik_rbac.py app/backend/tests/test_incidents_auth.py app/backend/tests/test_oidc_session_lifecycle.py -q` plus the listed shell tests; expected: all pass.
- [ ] Require zero cross-tenant reads/writes, complete protected-route matrix, administrative MFA/recovery, HTTP/SSE revocation, and dedicated service identities before marking Phase 1 approved.

### Task 3: Deliver the Zabbix-to-Hub-to-GLPI incident path

**Plans:**
- `docs/superpowers/plans/2026-09-18-phase-2-zabbix-glpi-operations.md`
- Phase 3 Task 3 in `docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md`

**Interfaces:** Phase 2 produces validated source events and one stable incident/ticket relationship. Phase 3 Task 3 provides durable idempotency and owner-safe concurrency. Both consume Phase 1 tenant authorization.

- [ ] Execute Phase 2 Tasks 1–5 in order, exactly as specified in its plan.
- [ ] Run each named Phase 2 test before its commit; expected: the synthetic alert-to-resolution flow creates or updates one GLPI ticket and retains its Hub link.
- [ ] Require source failure, stale data, unknown tenant, duplicate delivery and partial GLPI failure to remain visible and recoverable before marking the path complete.

### Task 4: Make Hub runtime failure visible

**Plan:** Tasks 2 and 3 in `docs/superpowers/plans/2026-09-18-phase-3-hub-runtime-reliability.md`.

**Interfaces:** Task 2 provides fail-closed container/API/worker readiness. Task 3 provides durable idempotency and owner-safe concurrency. Phase 3 Task 1 is already complete at `342a817`.

- [ ] Execute Phase 3 Tasks 2 and 3, following their exact test and commit instructions.
- [ ] Require worker/process/dependency failure to make readiness nonzero; require concurrent retry and replay to preserve one tenant-scoped incident/ticket relationship.
- [ ] Run task-level backend tests and lint commands specified by Phase 3 Tasks 2 and 3; expected: all pass.

### Task 5: Deliver the operator-facing MVP interface

**Plan:** Tasks 1–5 in `docs/superpowers/plans/2026-09-18-phase-4-dashboard-operational-truth.md`.

**Interfaces:** Consumes locally verified identity, source, incident and runtime contracts from Tasks 2–4. Produces authenticated incident list/detail, linked ticket, source health/freshness/error, and explicit states for unavailable modules. Production release still requires approved Phase 0–3 gates.

- [ ] Execute Phase 4 Tasks 1–5 in order; do not include its Wazuh sizing/purchase task in MVP delivery.
- [ ] Remove static security data and hard-coded timestamps from production routes; test stale, failed, empty and healthy source responses.
- [ ] Complete the operator journeys in Phase 4 Task 5 and its prescribed tests/build; expected: every displayed MVP value has a real source and freshness/error state.
- [ ] Keep Wazuh marked `planned` or `unavailable` until its separate rollout passes.

### Task 6: Close the production release gate and accept the MVP

**Plans:**
- `docs/superpowers/plans/2026-09-18-phase-0-recovery-release-baseline.md`
- `docs/superpowers/plans/2026-09-18-phase-6-integrated-acceptance.md`

**Interfaces:** Fase 0 produces a recoverable, reproducible and reversible production release. Phase 6 consumes approved Phase 0–4 gates and produces persona/tenant UAT, disaster recovery evidence and seven-day operational acceptance.

- [ ] Finish the four open Phase 0 items without repeating completed backup/restore work; verify current evidence age and hashes before relying on it.
- [ ] Require a clean, explicitly scoped release snapshot, immutable artifact identification, passing CI, backup/restore proof and rehearsed rollback before approving Fase 0. Preserve unrelated local files and user changes.
- [ ] After Fase 0 passes, execute Phase 3 Tasks 4 and 5, following their exact canary, rollback, stability and test steps; expected: failed canary restores prior release and required health metrics remain visible during the observation window.
- [ ] Run the final backend suite and Ruff/Black/MyPy commands specified by the Phase 3 gate; expected: all pass.
- [ ] Execute Phase 6 Tasks 1–5, including synthetic end-to-end tests for operator roles and allowed/denied tenants.
- [ ] Run Phase 6's integrated tests and seven-day observation; expected: all eight MVP criteria pass, with zero cross-tenant access, duplicate incidents/tickets, critical incidents without owner, stale backup or release divergence.
- [ ] Promote the MVP only after both gates pass; record release, residual risks and explicit Wazuh `planned` state.

### Task 7: Onboard Wazuh after MVP acceptance

**Plans:**
- `docs/superpowers/plans/2026-09-18-wazuh-4147-production-rollout.md`
- `docs/superpowers/plans/2026-09-18-wazuh-security-signal-ingestion.md`

**Interfaces:** The rollout plan produces a dedicated, recoverable Wazuh deployment in gated waves. The ingestion plan maps version-specific events to tenant-scoped `SecuritySignal` records; the MVP incident model consumes normalized signals and never raw Wazuh payloads.

- [ ] Do not start purchase or production rollout before MVP acceptance and explicit capacity/cost approval.
- [ ] Execute ingestion contract and adapter tasks before endpoint rollout; preserve observation mode and prohibit automatic external dispatch in the five-endpoint wave.
- [ ] Advance through 5 endpoints/48 hours, 25 endpoints/7 days, then at most 50 endpoints only when each wave gate passes.
- [ ] Require tenant isolation, idempotency, restore, endpoint overhead and no-loss evidence before each wave promotion.

## Delivery Boundaries

- MVP ends after Task 6. Task 7 is explicitly post-MVP.
- Incomplete infrastructure or security modules appear as unavailable/planned; they never block otherwise accepted MVP workflows unless they affect a listed MVP gate.
- No task may silently expand into mass Zabbix cleanup, Wazuh deployment, Contabo mutations, automated remediation or production writes outside its approved phase scope.
- Stop at the first failed gate. Record evidence and fix the owning task before proceeding.
