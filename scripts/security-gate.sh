#! /usr/bin/env bash

set -euo pipefail

MODE="${1:-warn}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$MODE" in
  warn|strict)
    ;;
  -h|--help)
    cat <<'EOF'
Usage:
  bash scripts/security-gate.sh [warn|strict]

Modes:
  warn    Print governed-secret findings but do not fail.
  strict  Fail when governed secrets use insecure defaults or short signing keys.
EOF
    exit 0
    ;;
  *)
    echo "[security-gate] invalid mode: $MODE" >&2
    exit 1
    ;;
esac

cd "$ROOT_DIR/backend"
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python app/check_security_config.py --mode "$MODE"
