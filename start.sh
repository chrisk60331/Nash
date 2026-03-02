#!/usr/bin/env bash
set -euo pipefail

echo "=== Nash — Starting ==="

# Clear built-in provider keys that may leak from shell env
unset OPENAI_API_KEY ANTHROPIC_API_KEY GOOGLE_KEY ASSISTANTS_API_KEY AZURE_API_KEY

# Install deps & build packages (skips if lockfile unchanged)
echo "→ Installing dependencies & building packages..."
npm run smart-reinstall

# Start backend (serves built frontend from client/dist/)
echo "→ Starting backend on http://localhost:3080/"
npm run backend:dev &
BACKEND_PID=$!

# Start frontend dev server with HMR
echo "→ Starting frontend dev server on http://localhost:3090/"
npm run frontend:dev &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "→ Shutting down..."
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  echo "=== Nash — Stopped ==="
}
trap cleanup EXIT INT TERM

wait
