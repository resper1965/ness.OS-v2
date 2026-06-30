# Upgrading n.infraops

Because **n.infraops** sits at the heart of our monitoring and automation infrastructure, keeping it updated is critical for security and performance. This guide outlines how updates and migrations are handled in the repository.

## 1. Automated Dependency Updates (Dependabot)
We use **Dependabot** to continuously scan our dependencies in both Python (`backend/requirements.txt`) and Node.js (`frontend/package.json`).
- Minor and patch updates are generated automatically via Pull Requests.
- The CI pipeline will automatically run linting and tests on these PRs.
- Maintainers should merge Dependabot PRs weekly after verifying the CI checks.

## 2. Upgrading the Zabbix NOC Infrastructure
Infrastructure changes to the Zabbix core must be performed via Ansible, not manually on the server.
1. Update the roles in `infra/ansible/roles/`.
2. Test the playbook on a staging VPS.
3. Apply to production:
   ```bash
   cd infra/ansible
   ansible-playbook -i inventory/hosts.yml playbooks/site.yml
   ```

## 3. Database Migrations (PostgreSQL/Timescale)
When altering the AIOps database schema:
- We use Alembic (Python) for schema migrations.
- **Never modify tables manually in production.**
- To apply migrations during a deployment:
  ```bash
  cd app/backend
  alembic upgrade head
  ```

## 4. Rollback Plan
Always ensure a fallback is available before a major upgrade:
1. **Database:** Ensure a pg_dump (or Timescale backup) was run within the last 24 hours.
2. **Containers:** If a new Docker image fails in production, revert the image tag in `docker-compose.yml` and run `docker compose up -d`.
