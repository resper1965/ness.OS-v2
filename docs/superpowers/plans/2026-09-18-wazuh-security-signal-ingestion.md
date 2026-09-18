# Wazuh Security Signal Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fail-closed, tenant-safe Wazuh 4.14.7 ingestion path that persists a versioned security signal before asynchronous triage.

**Architecture:** A pure Wazuh v4 adapter converts raw alerts to `SecuritySignalInput`; a machine endpoint authenticates, resolves the tenant, inserts an idempotent `SecuritySignal`, then queues its database ID. A dedicated worker processes the normalized record and preserves failures for retry.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL JSONB, Celery, Redis, pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-wazuh-production-entry-design.md`

## Global Constraints

- Wazuh production baseline is exactly `4.14.7`.
- Zabbix production ingestion must remain unchanged.
- Tenant identity is resolved through `TenantMapping`; request groups are not authorization.
- Accepted signals are committed before Celery dispatch.
- Automatic corrective action remains disabled.
- Raw Wazuh payloads never enter an AI prompt.

---

### Task 1: Define the SecuritySignal v1 contract and Wazuh 4 adapter

**Files:**
- Create: `app/backend/app/security_signals/__init__.py`
- Create: `app/backend/app/security_signals/contracts.py`
- Create: `app/backend/app/security_signals/wazuh_v4.py`
- Test: `app/backend/tests/test_wazuh_v4_adapter.py`

**Interfaces:**
- Consumes: raw `dict[str, Any]`, trusted `tenant_id: str`, `manager_id: str`.
- Produces: `normalize_wazuh_v4(payload, tenant_id, manager_id) -> SecuritySignalInput` and `SecuritySignalInput.idempotency_key() -> str`.

- [ ] **Step 1: Write failing adapter tests**

```python
def test_normalizes_real_wazuh_v4_shape():
    signal = normalize_wazuh_v4(
        {
            "id": "evt-1",
            "timestamp": "2026-09-18T10:00:00-03:00",
            "rule": {"id": "5712", "level": 15, "description": "SSH brute force"},
            "agent": {"id": "001", "name": "prod-dc", "groups": ["ness"]},
            "data": {"srcip": "203.0.113.10"},
        },
        tenant_id="ness",
        manager_id="wazuh-wave1",
    )
    assert signal.schema_version == 1
    assert signal.severity == 15
    assert signal.rule_id == "5712"
    assert signal.tenant_id == "ness"
    assert signal.observables.ip_addresses == ["203.0.113.10"]


def test_idempotency_is_tenant_scoped():
    first = fixture_signal(tenant_id="tenant-a").idempotency_key()
    second = fixture_signal(tenant_id="tenant-b").idempotency_key()
    assert first != second
```

- [ ] **Step 2: Run the tests and verify the contract is absent**

Run: `pytest -q tests/test_wazuh_v4_adapter.py`

Expected: collection fails because `app.security_signals` does not exist.

- [ ] **Step 3: Implement strict Pydantic contracts and normalization**

Define `SecuritySignalInput`, `SecurityObservables` and
`normalize_wazuh_v4`. Validate level `0..16`, require agent/rule IDs, parse a
timezone-aware timestamp, recursively extract only valid public IPs and
SHA-256/SHA-1/MD5 hashes, compute canonical JSON SHA-256, and never mutate the
input dictionary.

- [ ] **Step 4: Run focused quality checks**

Run: `pytest -q tests/test_wazuh_v4_adapter.py && ruff check app/security_signals tests/test_wazuh_v4_adapter.py`

Expected: all adapter tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit the contract**

```bash
git add app/backend/app/security_signals app/backend/tests/test_wazuh_v4_adapter.py
git commit -m "feat: add versioned Wazuh security signal adapter"
```

### Task 2: Persist idempotent security signals

**Files:**
- Modify: `app/backend/app/models/models.py`
- Modify: `app/backend/app/models/__init__.py`
- Create: `app/backend/sql/003_security_signals.sql`
- Test: `app/backend/tests/test_security_signal_model.py`

**Interfaces:**
- Consumes: `SecuritySignalInput` from Task 1.
- Produces: SQLAlchemy `SecuritySignal` with `from_input(signal)` and statuses `received`, `processing`, `processed`, `archived`, `failed`.

- [ ] **Step 1: Write model tests**

```python
def test_model_keeps_normalized_and_raw_fields_separate():
    model = SecuritySignal.from_input(fixture_signal(tenant_id="ness"))
    assert model.tenant_id == "ness"
    assert model.status == "received"
    assert model.raw_sha256
    assert model.raw_payload["rule"]["id"] == "5712"
```

- [ ] **Step 2: Run the model test and confirm failure**

Run: `pytest -q tests/test_security_signal_model.py`

Expected: import fails because `SecuritySignal` is not defined.

- [ ] **Step 3: Add the model and idempotent DDL**

Create `n_secops_security_signals` with a unique `idempotency_key`, indexed
`tenant_id`, source metadata, normalized fields, JSONB observables/raw payload,
status, attempt count, bounded error code and timestamps. Add check constraints
for schema version, severity and status. The SQL file uses `CREATE TABLE IF NOT
EXISTS` and `CREATE INDEX IF NOT EXISTS` so it can be applied repeatedly.

- [ ] **Step 4: Run focused tests and static checks**

Run: `pytest -q tests/test_security_signal_model.py && ruff check app/models tests/test_security_signal_model.py`

Expected: all checks pass.

- [ ] **Step 5: Commit persistence**

```bash
git add app/backend/app/models app/backend/sql/003_security_signals.sql app/backend/tests/test_security_signal_model.py
git commit -m "feat: persist idempotent security signals"
```

### Task 3: Add dedicated Wazuh machine ingestion

**Files:**
- Modify: `app/backend/app/config.py`
- Create: `app/backend/app/api/v1/security_signals.py`
- Modify: `app/backend/app/main.py`
- Test: `app/backend/tests/test_wazuh_ingestion.py`

**Interfaces:**
- Consumes: header `X-Api-Key`, query/header manager identity, Wazuh 4 JSON, database session.
- Produces: HTTP 202 `{signal_id, idempotency_key, accepted, duplicate}` and queues `process_security_signal(signal_id)`.

- [ ] **Step 1: Write endpoint tests**

Cover missing configuration (503), invalid key (401), unknown tenant mapping
(422), valid insert (202), exact replay (202 with `duplicate=true`) and a queue
failure (503 with the committed signal left in `received`). Use dependency
overrides and mocks; never require a live Redis or database.

- [ ] **Step 2: Run the endpoint tests and confirm failure**

Run: `pytest -q tests/test_wazuh_ingestion.py`

Expected: the router import or route lookup fails.

- [ ] **Step 3: Implement fail-closed authentication and tenant resolution**

Add `wazuh_ingest_api_key: str = ""` and `wazuh_manager_id: str = ""` to
settings. Resolve all received agent groups against `TenantMapping` records
where `external_platform == "wazuh"`; accept exactly one internal customer.
Use `verify_key`, normalize, insert with the unique key, commit, then dispatch
the database ID. Do not call triage, AI, GLPI or n8n in the request.

- [ ] **Step 4: Register the router and run focused tests**

Run: `pytest -q tests/test_wazuh_ingestion.py tests/test_webhook_auth.py`

Expected: all tests pass.

- [ ] **Step 5: Commit ingestion**

```bash
git add app/backend/app/config.py app/backend/app/api/v1/security_signals.py app/backend/app/main.py app/backend/tests/test_wazuh_ingestion.py
git commit -m "feat: ingest authenticated Wazuh security signals"
```

### Task 4: Process normalized signals asynchronously

**Files:**
- Create: `app/backend/app/workers/security_signals.py`
- Modify: `app/backend/app/workers/celery_app.py`
- Modify: `app/backend/app/core/triage_engine.py`
- Test: `app/backend/tests/test_security_signal_worker.py`

**Interfaces:**
- Consumes: `process_security_signal(signal_id: int)`.
- Produces: terminal signal status and one tenant-scoped `SocDecision` at most.

- [ ] **Step 1: Write worker behavior tests**

Cover missing records, already completed records, atomic claim, low-risk archive,
high-risk decision creation, transient retry, exhausted `failed` status and
tenant-scoped fingerprinting.

- [ ] **Step 2: Run the worker tests and confirm failure**

Run: `pytest -q tests/test_security_signal_worker.py`

Expected: task import fails.

- [ ] **Step 3: Implement normalized deterministic triage**

Add `evaluate_security_signal` to accept numeric severity, asset name and
normalized observables. Remove reliance on nested Wazuh fields for the new
pipeline. The task loads by ID, claims only `received`/retryable records,
increments attempts, persists the decision before dispatch and records bounded
error codes. It uses Celery autoretry with exponential backoff for transient
dependencies.

- [ ] **Step 4: Register the task and run tests**

Run: `pytest -q tests/test_security_signal_worker.py tests/test_triage_engine.py tests/test_soc_dispatch_audit.py`

Expected: new and legacy behavior pass.

- [ ] **Step 5: Commit asynchronous processing**

```bash
git add app/backend/app/workers/security_signals.py app/backend/app/workers/celery_app.py app/backend/app/core/triage_engine.py app/backend/tests/test_security_signal_worker.py
git commit -m "feat: process normalized security signals"
```

### Task 5: Enforce sanitized AI context and observation mode

**Files:**
- Modify: `app/backend/app/config.py`
- Modify: `app/backend/app/integrations/soc_agent.py`
- Create: `app/backend/app/security_signals/ai_context.py`
- Test: `app/backend/tests/test_security_signal_ai_context.py`

**Interfaces:**
- Consumes: normalized `SecuritySignal` and enrichment summary.
- Produces: allowlisted `dict[str, Any]` for AI; no raw payload.

- [ ] **Step 1: Write data-leak and observation-mode tests**

Include synthetic secrets in nested raw fields and assert they do not appear in
the serialized AI request. Assert `wazuh_observation_mode=true` prevents AI,
GLPI, n8n and notification calls while preserving triage and status.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest -q tests/test_security_signal_ai_context.py`

Expected: the allowlist module and setting are absent.

- [ ] **Step 3: Implement the allowlist and kill switch**

Add `wazuh_observation_mode: bool = True`. Build AI context only from IDs,
normalized title/severity/time, asset identity, sanitized observables and
bounded enrichment summaries. Change the new worker to honor observation mode.
Keep legacy interactive triage behavior compatible but route any new signal
through the allowlisted function.

- [ ] **Step 4: Run security-focused tests**

Run: `pytest -q tests/test_security_signal_ai_context.py tests/test_ai_context.py tests/test_sanitizer.py`

Expected: all tests pass and raw synthetic secrets are absent.

- [ ] **Step 5: Commit AI boundary controls**

```bash
git add app/backend/app/config.py app/backend/app/integrations/soc_agent.py app/backend/app/security_signals/ai_context.py app/backend/tests/test_security_signal_ai_context.py
git commit -m "fix: isolate raw Wazuh data from AI processing"
```

### Task 6: Add recovery, health and full verification

**Files:**
- Modify: `app/backend/app/workers/security_signals.py`
- Create: `app/backend/app/api/routers/security_signals.py`
- Modify: `app/backend/app/main.py`
- Test: `app/backend/tests/test_security_signal_recovery.py`
- Test: `app/backend/tests/test_security_signal_tenant_auth.py`

**Interfaces:**
- Consumes: stale `received`/`failed` records and authenticated NOC requests.
- Produces: republish task, tenant-filtered health counts and bounded failure codes.

- [ ] **Step 1: Write recovery and authorization tests**

Test that stale received records are republished once, recent records are left
alone, client roles see only their tenant and global NOC roles see aggregate
counts. Verify raw payload is absent from list and health responses.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest -q tests/test_security_signal_recovery.py tests/test_security_signal_tenant_auth.py`

Expected: recovery task and health route are absent.

- [ ] **Step 3: Implement recovery and health views**

Add `republish_stale_security_signals` and route it through Celery Beat or the
existing operational scheduler every five minutes. Add read-only health counts
by status with `resolve_tenant_scope`; expose no raw payload or exception text.

- [ ] **Step 4: Run the complete backend verification**

Run: `pytest -q && ruff check app tests && ruff format --check app tests && mypy app`

Expected: all commands exit zero.

- [ ] **Step 5: Commit recovery and health**

```bash
git add app/backend/app/workers/security_signals.py app/backend/app/api/routers/security_signals.py app/backend/app/main.py app/backend/tests/test_security_signal_recovery.py app/backend/tests/test_security_signal_tenant_auth.py
git commit -m "feat: recover and observe security signal processing"
```

