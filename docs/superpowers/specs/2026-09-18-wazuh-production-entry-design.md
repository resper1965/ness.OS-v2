# Wazuh 4.14.7 Production Entry Design

## Context

The existing Zabbix environment is production and must continue to be the
canonical source for availability. Wazuh has not yet been deployed. It will be
introduced beside Zabbix as the canonical security platform, starting with one
dedicated server and 25–50 real endpoints.

Wazuh 5.0 is still a pre-release and does not support an in-place manager
upgrade from 4.x. The first production release therefore uses Wazuh 4.14.7 but
keeps the Wazuh-specific event shape outside the ness.OS domain model.

## Goals

- Introduce Wazuh 4.14.7 without changing the Zabbix production path.
- Receive real Wazuh events through authenticated machine ingestion.
- Resolve every event to an explicit ness.OS tenant before processing.
- Persist accepted events before asynchronous triage and external dispatch.
- Prevent duplicate processing and cross-tenant correlation.
- Send only selected, sanitized fields to external AI providers.
- Make a later Wazuh 5 adapter replaceable without changing triage or GLPI.
- Begin with 5 endpoints in observation mode, then 25 and at most 50 endpoints.

## Non-goals

- High availability in the first Wazuh wave.
- Automatic active response or unattended remediation.
- Migrating the existing Zabbix incident pipeline.
- Deploying all approximately 624 endpoints in the first wave.
- Rewriting Wazuh 4 XML rules for Wazuh 5 before Wazuh 5 is stable.
- Migrating all Wazuh 4 raw history into Wazuh 5.

## Architecture

```text
Wazuh 4.14.7 integration
        |
        v
POST /api/v1/security-signals/wazuh/4
        |
        +-- API-key authentication
        +-- payload validation
        +-- explicit tenant mapping
        +-- Wazuh v4 normalization
        +-- idempotent database insert
        |
        v
SecuritySignal v1 --Celery--> deterministic triage
        |                         |
        |                         +--> sanitized enrichment / optional AI
        |                         +--> SocDecision
        |                         +--> GLPI / operator notification
        v
raw payload retained with checksum and restricted access
```

The Wazuh adapter owns all knowledge of Wazuh 4 fields. Consumers receive a
versioned `SecuritySignal` and never inspect `rule`, `agent`, or other raw Wazuh
objects. A Wazuh 5 adapter will map findings, WCS fields, UUID rules and textual
severity into the same contract.

## SecuritySignal v1

The internal contract contains:

- `schema_version`: exactly `1`;
- `source`: exactly `wazuh` for this adapter;
- `source_version`: exactly `4.14.7` for the first deployment;
- `source_event_id`: Wazuh event identifier when present;
- `tenant_id`: resolved from `TenantMapping`, never trusted from the request;
- `agent_id`, `agent_name`, `asset_id` and `asset_name`;
- `rule_id`, `rule_title`, numeric `severity` from 0 through 16;
- `occurred_at` and `received_at` as timezone-aware timestamps;
- normalized observables: public IP addresses and cryptographic hashes;
- `raw_sha256` and restricted `raw_payload`;
- `status`: `received`, `processing`, `processed`, `archived` or `failed`;
- `attempt_count` and a sanitized `last_error_code`.

The idempotency key is SHA-256 over
`tenant_id | source | manager_id | source_event_id`. If the source event has no
stable identifier, the adapter uses the raw event timestamp, agent ID, rule ID
and raw payload checksum. The database enforces uniqueness.

## Authentication and tenancy

The ingestion endpoint uses a dedicated `wazuh_ingest_api_key`; it does not
reuse browser authentication or the general Zabbix webhook key. Missing
configuration fails closed with HTTP 503, and an invalid key returns HTTP 401.

Each Wazuh agent group is mapped through `n_infraops_tenant_mappings` with
`external_platform = 'wazuh'`. The adapter rejects an unknown or ambiguous
mapping with HTTP 422 and does not enqueue the event. The raw group name is
evidence, not authorization.

Tenant ID is included in the idempotency key and every database query used for
correlation, decisions and listing. Cross-tenant tests are release blockers.

## Processing and failure behavior

The API normalizes and commits a signal before sending its database ID to
Celery. A queue failure returns HTTP 503 while leaving the signal in `received`;
a recovery task republishes received signals older than five minutes. Workers
claim a signal by moving it atomically to `processing` and ignore already
completed records.

Threat-intelligence, AI, GLPI and notification failures do not discard the
signal. The worker records a bounded error code, increments `attempt_count` and
retries transient failures with exponential backoff. Exhausted signals become
`failed` and appear in operational health. Raw exception text and secrets are
not stored in user-visible fields.

The deterministic triage engine operates on normalized fields. An archived
signal means “no incident created”; it must not be labeled a false positive.
AI receives an allowlisted context containing tenant-neutral signal fields and
sanitized observables. Automatic corrective action remains disabled.

## Wazuh infrastructure

Wave 1 uses one freshly installed, dedicated VPS running the official Wazuh
4.14.7 single-node Docker deployment. The playbook must be idempotent, avoid a
forced destructive Git update, expose the dashboard only through the approved
administrative path, and never expose indexer port 9200 publicly.

Agent ports 1514/TCP and 1515/TCP are limited to approved source networks.
Syslog 514/UDP is disabled unless a named source and use case are approved.
Secrets and generated certificates stay outside Git. Configuration, indexer
snapshots and restore instructions are backed up to the private Wazuh bucket.

## Production rollout

1. Prepare and verify the adapter, persistence, queue and deployment tooling
   without purchasing infrastructure.
2. Provision the dedicated VPS and install Wazuh 4.14.7.
3. Enroll 5 endpoints for 48 hours with GLPI, notifications, AI and active
   response disabled.
4. Expand to 25 endpoints and allow only high-confidence incidents to reach
   GLPI, always with human approval for action.
5. Observe for seven complete days, including a backup and isolated restore.
6. Expand to at most 50 endpoints and accept Wave 1.
7. Later waves follow `100 -> 25% -> 50% -> 100%`, each with its own hold point.

Rollout pauses if the Wazuh agent produces a sustained, material regression in
endpoint CPU, memory, network use or Zabbix collection. Rollback disables or
removes only the Wazuh agent and leaves Zabbix untouched.

## Acceptance criteria

- Wazuh 4.14.7 payload fixtures normalize into `SecuritySignal v1`.
- Unknown tenants, invalid keys and malformed events fail closed.
- Replayed events produce one signal and at most one downstream decision.
- Tenant A cannot read, correlate with or affect Tenant B.
- Queue and downstream outages preserve the accepted signal for retry.
- No unfiltered raw Wazuh payload is sent to AI.
- Observation mode creates no external ticket, message or corrective action.
- Backup and isolated restore are proven before the 25-endpoint wave is accepted.
- Every actionable rule has an owner, a runbook and a GLPI category.

## Wazuh 5 migration policy

Wazuh 5 is evaluated in parallel only after it reaches a stable release. Its
adapter must pass the same contract suite as the Wazuh 4 adapter. Custom Wazuh
4 rules are inventoried with fixtures and expected outcomes so that rewritten
Sigma/WCS rules can be compared behaviorally.

The production transition uses a new Wazuh 5 installation and a controlled
agent migration. ness.OS retains normalized signals, decisions and incident
links. Wazuh 4 raw history is preserved as immutable backup evidence for its
retention period rather than bulk-imported into Wazuh 5.

## Delivery split

- Plan 1 delivers the application boundary: contract, adapter, persistence,
  authenticated ingestion, asynchronous processing and safety tests.
- Plan 2 delivers the operational boundary: Wazuh 4.14.7 provisioning,
  firewall, backup/restore checks and the wave runbook.

