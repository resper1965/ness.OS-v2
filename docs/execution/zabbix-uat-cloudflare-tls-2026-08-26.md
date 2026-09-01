# Zabbix UAT — Cloudflare TLS

Date: 2026-08-26 (BRT)
Scope: `zabbix-uat.ness.com.br` on `ness-os-zabbix-prd-01` (`zbx-prd-01`).

## Result

- Cloudflare DNS record is proxied to the UAT origin.
- Cloudflare SSL/TLS mode is **Full (strict)**.
- A new Cloudflare Origin certificate was installed at the origin with its private key restricted to root; transient transfer files were removed from the origin.
- Apache serves the Zabbix frontend only on HTTPS externally; the upstream remains local loopback.
- UFW permits TCP/443 solely from the Cloudflare IPv4 network list applied at deployment time; SSH remains restricted separately.
- External validation returned HTTP/2 200 through Cloudflare, with the expected Cloudflare edge response and security headers.
- `zabbix-server` remains `inactive` and `masked`. This validation did not start collection, proxy connections, agents, actions, or notifications.

## Controls applied

- HSTS (one year, including subdomains), `X-Content-Type-Options: nosniff`, and a strict referrer policy are enabled at Apache.
- The UAT certificate material is not committed to this repository and is not documented here.
- The formerly exposed Origin certificate must remain revoked; only the replacement certificate may be trusted.

## Authentication gate — completed, pending final revocation

A **separate** Authentik SAML provider and application for UAT were created
and an end-to-end login was verified. The existing `zabbix-saml` provider was
not modified because it remains bound to the production hostname.

UAT service-provider values:

| Field | Value |
| --- | --- |
| ACS URL | `https://zabbix-uat.ness.com.br/zabbix/index_sso.php?acs` |
| SP entity ID / audience | `https://zabbix-uat.ness.com.br` |
| Authentik issuer | `https://sso.ness.com.br` |

The IdP endpoint, signing certificate and username mapping were taken from the
new UAT provider metadata and applied to the Zabbix frontend. Preserve the
temporary local break-glass account until the final access-control change,
when it will be revoked under an approved procedure.

## Operating requirement

Cloudflare publishes its proxy address ranges dynamically. Replace the applied origin allowlist through a reviewed, scheduled maintenance process whenever Cloudflare changes the published ranges; do not open port 443 to the Internet as a shortcut.
