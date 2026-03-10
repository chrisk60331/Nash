#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Nash 2.0 (Docker) ==="

# Kill any existing processes on port 3080
lsof -ti:3080 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Stop and remove any existing containers
docker compose down --remove-orphans 2>/dev/null || true

echo "Building Docker image..."
docker compose build

echo "Starting Nash..."
docker compose up -d

echo ""
echo "Waiting for health check..."
for i in {1..20}; do
  if curl -sf http://localhost:3080/api/health > /dev/null 2>&1; then
    echo "  Nash is healthy!"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "  Health check timed out. Showing logs:"
    docker compose logs --tail=50
    exit 1
  fi
  sleep 2
done

echo ""
echo "============================================"
echo "  Nash 2.0 running!"
echo "  Open: http://localhost:3080"
echo ""
echo "  Logs:  docker compose logs -f"
echo "  Stop:  docker compose down"
echo "============================================"
