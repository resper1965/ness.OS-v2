# Phase 1 Identity UAT Evidence

Status: **PENDING** — no live account session or role/tenant journey was run. Limited read-only API and public SSO prechecks are recorded below; no authenticated production session or production write was used.

Run account-based UAT only after the Phase 0 gate passes and dedicated UAT accounts are available. Record each result as `PASS` or `FAIL`; leave `PENDING` until the check runs. Never record usernames, passwords, cookies, bearer tokens, recovery codes, or raw response headers here.

## Run metadata

| Field | Value |
|---|---|
| Run date (UTC) | PENDING |
| Operator | PENDING |
| Release / commit | PENDING |
| Hub, GLPI, n8n, Zabbix versions | PENDING |
| Evidence bundle reference | PENDING |

## Identity and application checks

Use dedicated `admin`, `operator`, and `viewer` UAT accounts in two tenants plus one disabled account. Record role and tenant labels only; do not record account identifiers.

| App | Identity | Login / SSO | Direct access | Logout + copied-token revocation | Expiry / disabled account | Forged identity headers ignored |
|---|---|---|---|---|---|---|
| Hub | admin, operator, viewer | PENDING | PENDING | PENDING | PENDING | PENDING |
| GLPI | admin, operator, viewer | PENDING | PENDING | PENDING | PENDING | PENDING |
| n8n | admin, operator, viewer | PENDING | PENDING | PENDING | PENDING | PENDING |
| Zabbix UAT | admin, operator, viewer | PENDING | PENDING | PENDING | PENDING | PENDING |
| All apps | disabled account | PENDING | PENDING | PENDING | PENDING | PENDING |

## Tenant boundary checks

For each app, test tenant A identity against tenant B data and the reverse. Use one read and one write attempt per supported resource type. Record endpoint or resource class, status code, and a redacted evidence reference only.

| App | Tenant A cannot read/write tenant B | Tenant B cannot read/write tenant A | Result reference |
|---|---|---|---|
| Hub | PENDING | PENDING | PENDING |
| GLPI | PENDING | PENDING | PENDING |
| n8n | PENDING | PENDING | PENDING |
| Zabbix UAT | PENDING | PENDING | PENDING |

## Hub session details

Run `infra/scripts/hub-session-readiness.sh --execute-contained` with dedicated Hub UAT credentials. The probe must verify login, cookie attributes, `/me`, cookie-authenticated SSE, logout, cookie rejection, and rejection of a copied bearer token. It stores credentials and tokens only in a mode-`0600` temporary directory and removes that directory on exit.

The local Authentik precheck contract test simulates unauthenticated public probes and fails if GLPI responds as though a forged identity header authenticated the request. This does not prove header replacement during an authenticated session; that remains a live UAT check.

## Read-only Zabbix UAT API precheck — 2026-09-27

SSH to UAT `169.58.234.9` as `ness_admin` succeeded. The loopback
`apiinfo.version` request returned Zabbix `7.0.27`. The token from the AIOps
container, which is configured for the canonical instance, was sent through a
temporary SSH tunnel to call `template.get` on UAT. UAT returned JSON-RPC
`-32602`, `Invalid params.`, with `data=Not authorized.`. This proves that the
canonical token did not authenticate on UAT; it does not prove that the UAT
user role denies `template.get`, because no UAT-specific token was tested. The
public UAT URL returned HTTP 403 at the edge. The SSH tunnel was closed and its
local listener was gone afterward. No users, tokens, permissions, configuration,
or monitoring data were changed. This does not complete any account-based UAT
row above.

### Local automation verification — 2026-09-27

The Phase 1 backend gate selection passed: 39 tests. Authentik readiness,
Psono tooling, Authentik public-precheck contract, and Hub session-readiness
shell tests passed. These checks used static inspection and simulated `curl`;
they made no live requests and used no real identities. The Hub test confirmed
the default probe sends no network requests and that credentials are rejected
unless explicit execution is enabled. This verifies test plumbing only; all
live UAT rows above remain `PENDING`. No credentials, cookies, tokens, or raw
headers were recorded.

| Check | Result | Evidence reference |
|---|---|---|
| Login issues host-only Secure HttpOnly SameSite=Strict cookie | PENDING | PENDING |
| `/me` accepts the session before logout | PENDING | PENDING |
| SSE accepts cookie without token in URL | PENDING | PENDING |
| Logout clears cookie and invalidates session | PENDING | PENDING |
| Copied bearer JWT is rejected after logout | PENDING | PENDING |

## Sign-off

| Role | Name / ticket reference | Date | Result |
|---|---|---|---|
| UAT operator | PENDING | PENDING | PENDING |
| Security reviewer | PENDING | PENDING | PENDING |


### Public SSO precheck — 2026-09-27 22:38 UTC

`infra/scripts/authentik-public-precheck.sh` completed with `authentik_public_precheck=PASS`. Authentik health and Hub returned HTTP 200; unauthenticated GLPI, n8n and Zabbix UAT redirected to Authentik with HTTP 302. A GLPI request with forged identity headers also redirected anonymously to Authentik. These were unauthenticated, read-only public requests; no login, cookie, token, account, or configuration was used or changed.

`infra/tests/test-authentik-public-precheck.sh` and `infra/tests/test-hub-session-readiness.sh` passed locally. The shell files were normalized to LF only while running under WSL and restored immediately afterward. The live role, tenant, MFA, expiration, and revocation rows above remain pending because dedicated UAT accounts are unavailable.
