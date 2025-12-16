#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${CONTAINER:-savery-dragonfly}"

echo "SAVERY_DRAGONFLY_STARTING"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker start "${CONTAINER}"
else
  docker run -d \
    --name "${CONTAINER}" \
    -p 6379:6379 \
    --ulimit memlock=-1 \
    docker.dragonflydb.io/dragonflydb/dragonfly \
    --proactor_threads=2
fi

docker logs -f "${CONTAINER}" &
LOGS_PID="$!"
trap 'kill "${LOGS_PID}" >/dev/null 2>&1 || true' EXIT

for _ in {1..60}; do
  if (echo >/dev/tcp/127.0.0.1/6379) >/dev/null 2>&1; then
    echo "SAVERY_DRAGONFLY_READY"
    wait "${LOGS_PID}"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for Dragonfly on :6379" >&2
exit 1

