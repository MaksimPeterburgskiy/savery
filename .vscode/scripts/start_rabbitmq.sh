#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${CONTAINER:-savery-rabbit}"

echo "SAVERY_RABBITMQ_STARTING"

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker start "${CONTAINER}"
else
  docker run -d \
    --name "${CONTAINER}" \
    -p 5672:5672 \
    -p 15672:15672 \
    rabbitmq:3-management
fi

docker logs -f "${CONTAINER}" &
LOGS_PID="$!"
trap 'kill "${LOGS_PID}" >/dev/null 2>&1 || true' EXIT

for _ in {1..90}; do
  if docker exec "${CONTAINER}" rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
    echo "SAVERY_RABBITMQ_READY"
    wait "${LOGS_PID}"
    exit 0
  fi
  if (echo >/dev/tcp/127.0.0.1/5672) >/dev/null 2>&1; then
    echo "SAVERY_RABBITMQ_READY"
    wait "${LOGS_PID}"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for RabbitMQ readiness" >&2
exit 1
