#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

IMAGE="${IMAGE:-nash:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-nash-local}"
HOST_PORT="${HOST_PORT:-3080}"
CONTAINER_PORT="${CONTAINER_PORT:-3080}"
HEALTH_PATH="${HEALTH_PATH:-/health}"
WAIT_SECONDS="${WAIT_SECONDS:-60}"

echo "Starting Docker container"
echo "IMAGE=${IMAGE}"
echo "CONTAINER_NAME=${CONTAINER_NAME}"
echo "URL=http://127.0.0.1:${HOST_PORT}${HEALTH_PATH}"

# Remove prior local container state for this container name.
if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER_NAME}"; then
  docker rm -f "${CONTAINER_NAME}" >/dev/null
fi

docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:${CONTAINER_PORT}" \
  "${IMAGE}" >/dev/null

echo "Container started. Running health check..."

HEALTH_URL="http://127.0.0.1:${HOST_PORT}${HEALTH_PATH}"
START_TS="$(date +%s)"

while true; do
  HTTP_CODE="$(curl -s -o /tmp/nash-healthcheck-body-$$.txt -w "%{http_code}" "${HEALTH_URL}" || true)"
  NOW_TS="$(date +%s)"
  ELAPSED="$((NOW_TS - START_TS))"

  if [[ "${HTTP_CODE}" == "200" ]]; then
    echo "PASS: ${HEALTH_URL} returned HTTP 200 after ${ELAPSED}s"
    rm -f /tmp/nash-healthcheck-body-$$.txt
    exit 0
  fi

  if [[ "${ELAPSED}" -ge "${WAIT_SECONDS}" ]]; then
    echo "FAIL: ${HEALTH_URL} did not return HTTP 200 within ${WAIT_SECONDS}s (last=${HTTP_CODE})"
    echo "----- response body -----"
    cat /tmp/nash-healthcheck-body-$$.txt || true
    echo "----- container logs -----"
    docker logs "${CONTAINER_NAME}" || true
    rm -f /tmp/nash-healthcheck-body-$$.txt
    exit 1
  fi

  sleep 2
done
