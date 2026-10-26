# IaC tooling

No system installs: `infra/bin/tf` runs `hashicorp/terraform:1.9.8` in Docker; `infra/bin/ansible <cmd> ...`
runs `ansible-playbook|ansible-lint|ansible-inventory` from `infra/.venv` (built from `infra/requirements-iac.txt`, plus collections `ansible.posix`, `community.general`, `community.mysql` used by the roles).

## Environment variables (names only, from the environment or direnv; never committed)

- `TF_VAR_contabo_oauth2_client_id`, `TF_VAR_contabo_oauth2_client_secret`, `TF_VAR_contabo_oauth2_user`, `TF_VAR_contabo_oauth2_pass`
- `TF_VAR_ssh_public_key`
- `CONTABO_*` and `AWS_*` (e.g. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) when a remote S3 backend is used

The wrapper forwards every `TF_VAR_*`, `CONTABO_*` and `AWS_*` variable set in the caller's environment.

## Order: plan → guard → apply

1. `infra/bin/tf plan -var-file=environments/prod.tfvars -out=prod.tfplan` (contains secrets: never commit or share)
2. Run the plan guard (Task 1.1, `infra/scripts/tf-plan-guard.sh`): abort on any `destroy`/`replace` in production.
3. `infra/bin/tf apply tfplan` only after the plan was reviewed. Existing instances have `prevent_destroy = true`.

## Import

Existing resources enter state via `import` blocks (`imports.tf`) or `infra/bin/tf import <addr> <id>`; run `plan` afterwards and expect no diff.

## Safe destruction

Never `destroy` production. To retire a resource: remove `prevent_destroy` in its own reviewed PR, run `plan`, confirm the exact set in the guard, get explicit approval (window, GO, rollback), then apply.
