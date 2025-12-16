#!/usr/bin/env bash
set -euo pipefail

IMAGE="${IMAGE:-savery/postgres-postgis-pgvector:local}"
CONTAINER="${CONTAINER:-savery-postgres}"

echo "SAVERY_POSTGRES_STARTING"

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  docker build -t "${IMAGE}" -f infra/docker/postgres-pgvector.Dockerfile infra/docker
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker start "${CONTAINER}"
else
  docker run -d \
    --name "${CONTAINER}" \
    -p 5432:5432 \
    -e POSTGRES_DB=savery \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    "${IMAGE}"
fi

docker logs -f "${CONTAINER}" &
LOGS_PID="$!"
trap 'kill "${LOGS_PID}" >/dev/null 2>&1 || true' EXIT

for _ in {1..90}; do
  if docker exec "${CONTAINER}" pg_isready -U postgres -d savery >/dev/null 2>&1; then
    echo "SAVERY_POSTGRES_READY"
    wait "${LOGS_PID}"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for Postgres readiness" >&2
exit 1

