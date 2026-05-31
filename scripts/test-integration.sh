#!/usr/bin/env bash
#
# Project-level integration-harness command (invoked by `npm run test:integration`).
#
# Idempotent: brings up the fixture compose, waits for every service to be
# ready, runs the integration suite, captures the exit code, tears the compose
# down regardless of pass/fail, and exits with the captured code.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/tests/integration/docker-compose.fixtures.yml"
PROJECT="pidtest"
MINIO_HEALTH_URL="http://localhost:59000/minio/health/ready"

compose() {
  docker compose -f "$COMPOSE_FILE" -p "$PROJECT" "$@"
}

cleanup() {
  echo "==> Tearing down fixture containers"
  compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Wait until a command succeeds, retrying once per second.
wait_for() {
  local label="$1"; shift
  local retries=60 i=0
  until "$@" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge "$retries" ]; then
      echo "ERROR: $label not ready after ${retries}s" >&2
      return 1
    fi
    sleep 1
  done
  echo "==> $label ready"
}

echo "==> Starting fixture services (Postgres / Redis / MinIO)"
compose up -d

echo "==> Polling service readiness"
wait_for "postgres" docker exec pidtest-postgres pg_isready -U pidtest -d pidtest
wait_for "redis" docker exec pidtest-redis redis-cli ping
wait_for "minio" curl -fsS "$MINIO_HEALTH_URL"

# Wait for the one-shot bucket-creation sidecar to finish successfully.
echo "==> Waiting for MinIO bucket creation"
i=0
until [ "$(docker inspect -f '{{.State.Status}}' pidtest-minio-setup 2>/dev/null)" = "exited" ]; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    echo "ERROR: minio-setup did not complete" >&2
    docker logs pidtest-minio-setup || true
    exit 1
  fi
  sleep 1
done
setup_code="$(docker inspect -f '{{.State.ExitCode}}' pidtest-minio-setup)"
if [ "$setup_code" != "0" ]; then
  echo "ERROR: minio-setup exited with code $setup_code" >&2
  docker logs pidtest-minio-setup || true
  exit 1
fi
echo "==> MinIO bucket ready"

echo "==> Installing backend test dependencies (poetry)"
poetry -C "$REPO_ROOT/backend" install --no-interaction --no-root

echo "==> Running integration smoke suite"
set +e
poetry -C "$REPO_ROOT/backend" run pytest "$REPO_ROOT/tests/integration" -v
TEST_EXIT=$?
set -e

echo "==> Integration suite exited with code $TEST_EXIT"
exit "$TEST_EXIT"
