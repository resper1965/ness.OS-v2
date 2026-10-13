#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

# Fail closed if the dedicated builder lacks any former CI gate.
gitleaks git --redact --no-banner --log-level error .
python3 -m black --check app/backend
python3 -m flake8 app/backend --count --select=E9,F63,F7,F82 --show-source --statistics
python3 -m ruff check app/backend/app
python3 -m ruff format --check app/backend/app
python3 -m mypy app/backend/app --ignore-missing-imports
python3 -m pytest -q app/backend/tests
npm ci --prefix app/frontend
npm run lint --prefix app/frontend
npm run build --prefix app/frontend
