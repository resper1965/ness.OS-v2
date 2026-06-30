# Security Policy

At **ness.**, security is our highest priority, especially since our AIOps platform orchestrates critical infrastructure operations. We take all security vulnerabilities seriously.

## Supported Versions

Currently, only the `main` branch (which reflects our production environment) receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |
| `< 1.0` | :x:                |

## Reporting a Vulnerability

**DO NOT report security vulnerabilities via public GitHub issues.**

If you discover a security vulnerability in `n-infraops`, please send an email directly to **security@ness.com.br**.

Please include the following in your report:
- A description of the vulnerability.
- Steps to reproduce the vulnerability.
- The potential impact of the vulnerability.

### Response SLA
You should receive a confirmation of your report within 24 hours. We will strive to provide a timeline for a fix within 72 hours. Once the issue is resolved, we will publish a security advisory and notify users.

## Secure Coding Practices
Our development workflow strictly enforces:
- Secrets must never be committed. We use `.env` files in development and secure secret managers in production.
- All webhook inputs (from Zabbix, Wazuh) must be sanitized before processing.
- The AIOps Database (PostgreSQL) must not be exposed to the public internet.
