# Contabo inventory read-only check — 2026-09-27

**Collected:** 2026-09-27 15:29 UTC (12:29 BRT) for Contabo API; SSH follow-up later in the same session.
**Scope:** Contabo compute inventory and firewall configuration, read-only. No VPS, firewall, DNS, storage, or credential settings were changed.

## Results

OAuth succeeded using the local Contabo API credential source. `GET /v1/compute/instances` returned four account instances; three belong to ness.OS and one pentest instance was excluded from project scope per the owner's instruction.

| Project instance | IPv4 | Contabo status |
|---|---|---|
| `ninfraops-zabbix` | `144.91.72.202` | `running` |
| `aiops` | `144.91.115.242` | `running` |
| `ness-os-zabbix-prd-01` | `169.58.234.9` | `running` |

`GET /v1/firewalls` showed the Contabo firewall named `ness` associated with `ninfraops-zabbix`, but the firewall status is `inactive`. Its stored inbound TCP/22 rule is marked active and accepts `0.0.0.0/0` and `::/0`. Since the firewall itself is inactive, this does not explain the SSH timeout and is not proof of the effective host firewall. Do not enable this firewall or alter its rule as part of this check.

SSH to `144.91.72.202:22` timed out before authentication. The as-built runbook documents port `2222`; on that port the host was reachable, but `ness_admin` authentication with the documented PPK-derived key returned `Permission denied (publickey)`. No remote command ran. The temporary converted key was removed and the source PPK was left unchanged. Contabo reports the VPS as running; SSH service, host firewall, and routing remain unverified.

## Limits

This check refreshes only Contabo instance inventory and the provider firewall view. It does not refresh production file hashes or image digests, test the Zabbix API token, prove OS-level reachability, or authorize deployment/cutover. The Phase 0 release gate remains **FAIL**.
