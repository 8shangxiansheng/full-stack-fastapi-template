#! /usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_TIME="$(date +"%Y%m%d-%H%M%S")"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/performance/reports/$REPORT_TIME}"

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000/api/v1}"
LOGIN_USERNAME="${LOGIN_USERNAME:-demo@example.com}"
LOGIN_PASSWORD="${LOGIN_PASSWORD:-changethis}"
PAYMENT_CALLBACK_SIGNING_SECRET="${PAYMENT_CALLBACK_SIGNING_SECRET:-changethis}"
PAYMENT_PROVIDER="${PAYMENT_PROVIDER:-mockpay}"
K6_VUS="${K6_VUS:-5}"
K6_DURATION="${K6_DURATION:-30s}"
THINK_TIME_MS="${THINK_TIME_MS:-200}"

mkdir -p "$REPORT_DIR"
cp "$ROOT_DIR/performance/report-template.md" "$REPORT_DIR/report.md"

run_with_local_k6() {
  k6 run \
    --summary-export "$REPORT_DIR/summary.json" \
    "$ROOT_DIR/performance/k6/order-baseline.js"
}

run_with_docker_k6() {
  local docker_api_base_url="$API_BASE_URL"

  docker_api_base_url="${docker_api_base_url/127.0.0.1/host.docker.internal}"
  docker_api_base_url="${docker_api_base_url/localhost/host.docker.internal}"

  docker run --rm \
    -v "$ROOT_DIR:/workdir" \
    -w /workdir \
    -e API_BASE_URL="$docker_api_base_url" \
    -e LOGIN_USERNAME \
    -e LOGIN_PASSWORD \
    -e PAYMENT_CALLBACK_SIGNING_SECRET \
    -e PAYMENT_PROVIDER \
    -e K6_VUS \
    -e K6_DURATION \
    -e THINK_TIME_MS \
    grafana/k6:0.49.0 run \
    --summary-export "$REPORT_DIR/summary.json" \
    /workdir/performance/k6/order-baseline.js
}

{
  echo "performance baseline"
  echo "report dir: $REPORT_DIR"
  echo "api base url: $API_BASE_URL"
  echo "vus: $K6_VUS"
  echo "duration: $K6_DURATION"
} | tee "$REPORT_DIR/summary.txt"

export API_BASE_URL LOGIN_USERNAME LOGIN_PASSWORD PAYMENT_CALLBACK_SIGNING_SECRET PAYMENT_PROVIDER
export K6_VUS K6_DURATION THINK_TIME_MS

if command -v k6 >/dev/null 2>&1; then
  run_with_local_k6 | tee -a "$REPORT_DIR/summary.txt"
else
  echo "k6 binary not found, fallback to Docker image grafana/k6:0.49.0" | tee -a "$REPORT_DIR/summary.txt"
  run_with_docker_k6 | tee -a "$REPORT_DIR/summary.txt"
fi

echo "report template copied to $REPORT_DIR/report.md" | tee -a "$REPORT_DIR/summary.txt"
