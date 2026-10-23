#!/usr/bin/env bash
# Local CI: same checks as .github/workflows (backend CI, lint, frontend CI), run on the dev machine.
# Usage: scripts/ci-local.sh [--backend] [--frontend] [--docker]
#   no flag = backend + frontend; --docker also builds the frontend release image.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
CACHE=${CI_LOCAL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/ci-local/ness.OS-v2}

do_backend=0; do_frontend=0; do_docker=0
for a in "$@"; do
  case $a in
    --backend) do_backend=1 ;;
    --frontend) do_frontend=1 ;;
    --docker) do_docker=1 ;;
    *) echo "usage: $0 [--backend] [--frontend] [--docker]" >&2; exit 2 ;;
  esac
done
if (( ! do_backend && ! do_frontend )); then do_backend=1; do_frontend=1; fi

die() { echo "ci-local: setup failed: $*" >&2; exit 1; }

# Runs every check even after a failure and lists the failed ones at the end.
failed=()
step() { # step <label> <command...>
  local label=$1; shift
  echo "-- $label"
  "$@" || failed+=("$label")
}

backend() {
  echo "== backend"
  mkdir -p "$CACHE" || die "mkdir cache"
  [[ -x $CACHE/venv/bin/python ]] || python3 -m venv "$CACHE/venv" || die "python3 -m venv"
  # shellcheck source=/dev/null
  . "$CACHE/venv/bin/activate"
  cd "$ROOT/app/backend" || die "cd backend"
  python -m pip install -q --upgrade pip || die "pip upgrade"
  pip install -q -r requirements.txt flake8 pytest pytest-asyncio black ruff mypy || die "pip install"
  step "backend: black" black --check .
  step "backend: flake8" flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
  step "backend: ruff check" ruff check app/
  step "backend: ruff format" ruff format --check app/
  step "backend: mypy" mypy app/ --ignore-missing-imports
  step "backend: pytest" pytest
}

frontend() {
  echo "== frontend"
  cd "$ROOT/app/frontend" || die "cd frontend"
  step "frontend: npm ci" npm ci
  step "frontend: lint" npm run lint
  step "frontend: build" npm run build
  if (( do_docker )); then step "frontend: docker build" docker build --file Dockerfile .; fi
}

(( do_backend )) && backend
(( do_frontend )) && frontend
if (( ${#failed[@]} )); then
  echo "ci-local: FAILED"; printf '  - %s
' "${failed[@]}"; exit 1
fi
echo "ci-local: ok"
