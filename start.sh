#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "=== Nash 2.0 ==="

# Kill any existing processes on our ports
lsof -ti:3080 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3090 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Install Python dependencies
echo "Installing Python dependencies..."
uv sync --quiet 2>/dev/null || uv sync

# Install Node dependencies and build packages
echo "Installing Node dependencies..."
npm install --silent 2>/dev/null || npm install

echo "Building frontend packages..."
npx turbo run build \
  --filter=librechat-data-provider \
  --filter=@librechat/data-schemas \
  --filter=@librechat/client \
  > /dev/null 2>&1 \
  && echo "  Packages built successfully." \
  || { echo "  Package build failed! Check with: npx turbo run build --filter=librechat-data-provider"; exit 1; }

# Start Python backend with the same Gunicorn/Gevent stack used in Docker.
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY suppresses the macOS fork-safety crash
# that kills gevent workers on Apple Silicon / macOS 12+.
echo "Starting Python API on :3080 with gunicorn..."
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES uv run gunicorn \
  --bind 0.0.0.0:3080 \
  --workers 1 \
  --worker-class gevent \
  --worker-connections 1000 \
  "api.app:create_app()" > /tmp/nash-api.log 2>&1 &
API_PID=$!
sleep 2

if ! kill -0 $API_PID 2>/dev/null; then
  echo "ERROR: API failed to start. Logs:"
  cat /tmp/nash-api.log
  exit 1
fi
echo "  API running (pid $API_PID)"

# Start frontend dev server
echo "Starting frontend on :3090..."
npm run frontend > /tmp/nash-frontend.log 2>&1 &
FE_PID=$!
sleep 3

if ! kill -0 $FE_PID 2>/dev/null; then
  echo "ERROR: Frontend failed to start. Logs:"
  cat /tmp/nash-frontend.log
  exit 1
fi
echo "  Frontend running (pid $FE_PID)"

echo ""
echo "============================================"
echo "  Nash 2.0 running!"
echo "  Open: http://localhost:3090"
echo "  API:  http://localhost:3080"
echo ""
echo "  Logs: tail -f /tmp/nash-api.log"
echo "        tail -f /tmp/nash-frontend.log"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $API_PID $FE_PID 2>/dev/null; exit 0" INT TERM
wait
