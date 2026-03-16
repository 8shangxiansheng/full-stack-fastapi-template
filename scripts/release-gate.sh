#! /usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-full}"
POSTGRES_PASSWORD_VALUE="${POSTGRES_PASSWORD:-changethis}"
COMPOSE_FILES=(-f compose.yml -f compose.override.yml)

usage() {
  cat <<'EOF'
Usage:
  bash scripts/release-gate.sh [full|fast]

Modes:
  full  Run compose health checks, OpenAPI client generation, backend tests,
        frontend build, and Playwright end-to-end tests.
  fast  Run compose health checks, OpenAPI client generation, backend tests,
        and frontend build. Skip Playwright.
EOF
}

require_command() {
  local command_name="$1"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "[release-gate] missing required command: $command_name" >&2
    exit 1
  fi
}

run_step() {
  local label="$1"
  shift

  echo
  echo "[release-gate] >>> $label"
  "$@"
  echo "[release-gate] <<< $label"
}

ensure_stack() {
  docker compose "${COMPOSE_FILES[@]}" up -d --wait db backend frontend adminer mailcatcher
}

check_backend_health() {
  curl --fail --silent http://127.0.0.1:8000/api/v1/utils/health-check/ >/dev/null
}

check_frontend_health() {
  curl --fail --silent http://127.0.0.1:5173 >/dev/null
}

generate_client() {
  bash scripts/generate-client.sh
}

run_backend_tests() {
  (
    cd backend
    UV_CACHE_DIR=/tmp/uv-cache POSTGRES_PASSWORD="$POSTGRES_PASSWORD_VALUE" uv run pytest tests/ -q
  )
}

run_frontend_build() {
  (
    cd frontend
    bun run build
  )
}

run_playwright() {
  docker compose "${COMPOSE_FILES[@]}" run --rm playwright \
    bunx playwright test --fail-on-flaky-tests --trace=retain-on-failure
}

case "$MODE" in
  full|fast)
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    echo "[release-gate] invalid mode: $MODE" >&2
    usage
    exit 1
    ;;
esac

require_command docker
require_command curl
require_command bun
require_command uv

cd "$ROOT_DIR"

echo "[release-gate] mode=$MODE"

run_step "Ensure compose stack" ensure_stack
run_step "Backend health check" check_backend_health
run_step "Frontend health check" check_frontend_health
run_step "Generate OpenAPI client" generate_client
run_step "Backend pytest" run_backend_tests
run_step "Frontend build" run_frontend_build

if [[ "$MODE" == "full" ]]; then
  run_step "Playwright end-to-end" run_playwright
fi

echo
echo "[release-gate] all checks passed"
