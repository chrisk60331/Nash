#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

unset OPENAI_API_KEY
echo "=== Stopping any existing servers on :3080 and :3090 ==="
lsof -ti:3080 | xargs kill -15 2>/dev/null || true
lsof -ti:3090 | xargs kill -15 2>/dev/null || true
sleep 3

echo "=== Clearing Turborepo cache ==="
rm -rf .turbo node_modules/.cache/turbo /tmp/backboard-uploads

echo "=== Building all packages (clean) ==="
npm run build

echo "=== Starting backend (port 3080) ==="
npm run backend &
BE_PID=$!

sleep 5

echo "=== Starting frontend dev server (port 3090) ==="
npm run frontend:dev &
FE_PID=$!
echo "=== Backend PID: $BE_PID | Frontend PID: $FE_PID ==="
echo "=== Backend: http://localhost:3080  |  Frontend: http://localhost:3090 ==="

wait
