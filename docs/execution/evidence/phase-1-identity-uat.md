# Phase 1 Identity UAT Evidence

Status: **PENDING** — template only; no live account or production request was used.

Run only after the Phase 0 gate passes and dedicated UAT accounts are available. Record each result as `PASS` or `FAIL`; leave `PENDING` until the check runs. Never record usernames, passwords, cookies, bearer tokens, recovery codes, or raw response headers here.

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
