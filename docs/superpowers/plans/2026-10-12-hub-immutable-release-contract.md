# Hub Immutable Release Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Hub/AIOps production Compose and release manifest capable of identifying exact immutable images before deployment, without changing the running AIOps host.

**Architecture:** Production Compose becomes an image-only contract: API and both workers share one mandatory immutable API image; frontend has its own mandatory immutable image. A development-only override retains local builds and source bind mounts. The manifest accepts an explicit Compose scope and service-image references so a candidate can be evidenced before deployment.

**Tech Stack:** Docker Compose v2, Bash, Python 3.12, pytest, GitHub Actions.

**Spec:** `docs/execution/implementation-plan-2026-10-11.md`, `docs/runbooks/release-and-rollback.md`, and `docs/execution/project-stage-2026-10-11.md`.

## Global Constraints

- Do not deploy, publish images, change the AIOps host, change DNS, or alter secrets.
- Production images match `registry/name@sha256:<64 lowercase hexadecimal characters>`; mutable tags fail.
- `api`, `worker-alerts`, and `worker-ml` use the same `NINF_API_IMAGE`; `frontend` uses `NINF_FRONTEND_IMAGE`.
- Production Compose has neither `build:` nor source-code bind mounts for those four services.
- Local development remains available only through `app/docker-compose.dev.yml`.
- The manifest records presence only for secret-like facts; no new dependency is added.

## Review Focus

- Mutable image references must fail before manifest creation; Task 1.
- A service override absent from the selected Compose must fail, not be ignored; Task 1.
- The three API-process services must not use different image references; Task 1.
- Production Compose must not regain `build:` or a source bind mount; Task 2.
- Development Compose must override release references so local compose config does not require production images; Task 2.

---

### Task 1: Scope and freeze the release manifest

**Files:**
- Modify: `infra/scripts/ness-release-manifest.py`
- Modify: `infra/tests/test-ness-release-manifest.py`
- Modify: `docs/runbooks/release-and-rollback.md`

**Interfaces:** `python3 infra/scripts/ness-release-manifest.py --output PATH --compose-file PATH [--compose-file PATH ...] --image-ref SERVICE=REFERENCE`; `--image-ref` is repeatable and its reference must match `^.+@sha256:[0-9a-f]{64}$`.

- [ ] **Step 1: Write failing pytest cases**

Add `test_explicit_compose_scope_ignores_unselected_files`, `test_manifest_accepts_immutable_service_image_override`, `test_manifest_rejects_mutable_service_image_override`, `test_manifest_rejects_unknown_override_service`, and `test_manifest_rejects_different_api_worker_image_override`.

- [ ] **Step 2: Run the new cases**

Run: `python3 -m pytest -q infra/tests/test-ness-release-manifest.py -k 'explicit_compose_scope or service_image_override'`  
Expected: FAIL because the CLI has no scoped Compose or service-image contract.

- [ ] **Step 3: Implement the minimal contract**

Add parser arguments and pure validation that scopes discovery to requested files, replaces only selected service image references, rejects unknown services, and rejects inconsistent API-worker references before writing output.

- [ ] **Step 4: Verify Task 1**

Run: `python3 -m pytest -q infra/tests/test-ness-release-manifest.py`  
Expected: PASS.

- [ ] **Step 5: Update the runbook and commit**

Use explicit production Compose files and four service-image arguments; state that image publication is an approved external workflow.

```bash
git add infra/scripts/ness-release-manifest.py infra/tests/test-ness-release-manifest.py docs/runbooks/release-and-rollback.md
git commit -m "feat(release): scope immutable image manifests"
```

### Task 2: Separate production images from development builds

**Files:**
- Modify: `app/docker-compose.yml`
- Create: `app/docker-compose.dev.yml`
- Create: `infra/tests/test-release-compose-contract.sh`

**Interfaces:** Production Compose requires `NINF_API_IMAGE` for API and both workers and `NINF_FRONTEND_IMAGE` for frontend. `app/docker-compose.dev.yml` supplies `ness-api:dev`, `ness-frontend:dev`, existing builds, and existing source mounts.

- [ ] **Step 1: Write the failing contract test**

Create a shell test asserting production has the four required image references and no production build/source mount; development has three API builds, frontend build, and both original source mounts.

- [ ] **Step 2: Run the contract test**

Run: `bash infra/tests/test-release-compose-contract.sh`  
Expected: FAIL because production currently contains builds and bind mounts.

- [ ] **Step 3: Make the smallest Compose split**

Move only the local-build and source-bind-mount settings for API, both workers, and frontend to `app/docker-compose.dev.yml`. Preserve production networks, healthchecks, environment, volumes, dependencies, limits, and external services.

- [ ] **Step 4: Verify Task 2 and commit**

Run: `bash infra/tests/test-release-compose-contract.sh`  
Expected: PASS.

```bash
git add app/docker-compose.yml app/docker-compose.dev.yml infra/tests/test-release-compose-contract.sh
git commit -m "feat(release): separate production images from dev builds"
```

### Task 3: Enforce the release contract in CI

**Files:**
- Modify: `.github/workflows/ci-backend.yml`
- Modify: `.github/workflows/ci-sbom.yml`
- Modify: `infra/tests/test-release-compose-contract.sh`

**Interfaces:** Backend CI validates production and development Compose with non-secret fixture values. SBOM builds the backend/frontend sources that later become the immutable artifacts; it does not publish them.

- [ ] **Step 1: Write a failing workflow assertion**

Extend `test-release-compose-contract.sh` to require a contract-test invocation and immutable placeholder values for both image variables in `ci-backend.yml`.

- [ ] **Step 2: Run the assertion**

Run: `bash infra/tests/test-release-compose-contract.sh`  
Expected: FAIL because CI lacks image references and the contract test.

- [ ] **Step 3: Update CI minimally**

Add two non-secret digest-shaped placeholders and the contract-test invocation to the existing Compose validation step. Modify SBOM only if the Compose split changes a build context; add no registry credential or publish step.

- [ ] **Step 4: Verify Task 3 and commit**

Run: `bash infra/tests/test-release-compose-contract.sh && python3 -m pytest -q infra/tests/test-ness-release-manifest.py && bash infra/tests/test-aiops-runtime-preflight.sh`  
Expected: PASS.

```bash
git add .github/workflows/ci-backend.yml .github/workflows/ci-sbom.yml infra/tests/test-release-compose-contract.sh
git commit -m "test(release): enforce immutable compose contract"
```

## Execution boundary

Registry publication, AIOps deployment, database migration, and rollback rehearsal are excluded. They are external/security-sensitive actions requiring an approved registry, GLPI change, release candidate digests, backup identifier, maintenance window, and rollback operator.

## Self-review

- Tasks 1–3 cover scope, immutable image inputs, dev/prod separation, and CI enforcement.
- Task 1 produces the CLI used by the runbook; Task 2 produces image variables consumed by CI; Task 3 supplies fixture values and enforcement.
- Every Review Focus failure mode has a test in Task 1 or Task 2.
- The plan deliberately excludes registry and production operations rather than simulating them.
