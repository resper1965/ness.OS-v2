# IaC tooling

No system installs: `infra/bin/tf` runs `hashicorp/terraform:1.9.8` in Docker; `infra/bin/ansible <cmd> ...`
runs `ansible-playbook|ansible-lint|ansible-inventory` from `infra/.venv` (built from `infra/requirements-iac.txt`, plus collections `ansible.posix`, `community.general`, `community.mysql` used by the roles).

## Environment variables (names only, from the environment or direnv; never committed)

- `TF_VAR_contabo_oauth2_client_id`, `TF_VAR_contabo_oauth2_client_secret`, `TF_VAR_contabo_oauth2_user`, `TF_VAR_contabo_oauth2_pass`
- `CONTABO_*` and `AWS_*` (e.g. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) when a remote S3 backend is used

The wrapper forwards every `TF_VAR_*`, `CONTABO_*` and `AWS_*` variable set in the caller's environment.

## Order: plan → guard → apply

1. `infra/bin/tf plan -var-file=environments/prod.tfvars -out=prod.tfplan` (contains secrets: never commit or share)
2. `infra/bin/tf show -json prod.tfplan | infra/scripts/tf-plan-guard.sh -`: exit 1 on any delete, replace or forget. Pipe it; the JSON holds the credentials in clear.
3. `infra/bin/tf apply prod.tfplan` only after a human read the plan: the guard does not stop in-place updates such as `product_id` or `total_purchased_space_tb`, which change billing. Every VPS and the Object Storage have `prevent_destroy = true`; `image_id`, `ssh_keys`, `default_user` and `region` are in `ignore_changes` (the provider does not read them back on import and changing them would force a replace).

## Import

Existing resources enter state via `import` blocks (`imports.tf`) or `infra/bin/tf import <addr> <id>`; run `plan` afterwards and expect no diff. Currently imported: `contabo_instance.vps[zabbix_prod|aiops|zabbix_uat]` and `contabo_object_storage.data_storage`. Keep `-var-file=environments/prod.tfvars` in every command.

## Safe destruction

Never `destroy` production. To retire a resource: remove `prevent_destroy` in its own reviewed PR, run `plan`, confirm the exact set in the guard, get explicit approval (window, GO, rollback), then apply.

## Estado remoto

`s3://ness-os-tfstate/prod/terraform.tfstate` (Contabo `eu2`, privado, versionado; criado em 27/10). Sem lock: rode um `plan`/`apply` por vez. Recuperar versão anterior (credenciais de `/srv/dev/secrets/projetos.env` no ambiente):

```bash
S3='docker run --rm -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_DEFAULT_REGION=default -v /tmp/opencode:/out amazon/aws-cli:2.22.35 --endpoint-url https://eu2.contabostorage.com'
$S3 s3api list-object-versions --bucket ness-os-tfstate --prefix prod/terraform.tfstate --query 'Versions[].[VersionId,LastModified]' --output text
$S3 s3api get-object --bucket ness-os-tfstate --key prod/terraform.tfstate --version-id <VersionId> /out/terraform.tfstate
```

