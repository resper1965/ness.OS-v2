#!/usr/bin/env bash
# Local CI: same checks as .github/workflows (backend CI, lint, frontend CI), run on the dev machine.
# Usage: scripts/ci-local.sh [--backend] [--frontend] [--docker]
#   no flag = backend + frontend; --docker also builds the frontend release image.
set -euo pipefail
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

backend() {
  echo "== backend"
  mkdir -p "$CACHE"
  [[ -x $CACHE/venv/bin/python ]] || python3 -m venv "$CACHE/venv"
  # shellcheck source=/dev/null
  . "$CACHE/venv/bin/activate"
  cd "$ROOT/app/backend"
  python -m pip install -q --upgrade pip
  pip install -q -r requirements.txt flake8 pytest pytest-asyncio black ruff mypy
  black --check .
  flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
  ruff check app/
  ruff format --check app/
  mypy app/ --ignore-missing-imports
  pytest
}

frontend() {
  echo "== frontend"
  cd "$ROOT/app/frontend"
  npm ci
  npm run lint
  npm run build
  if (( do_docker )); then docker build --file Dockerfile .; fi
}

(( do_backend )) && backend
(( do_frontend )) && frontend
echo "ci-local: ok"
