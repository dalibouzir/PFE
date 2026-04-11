#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
  cd "$ROOT_DIR/backend"
  source .venv/bin/activate
  PYTHONPATH="$ROOT_DIR" uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
BACK_PID=$!

(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &
FRONT_PID=$!

cleanup() {
  kill "$BACK_PID" "$FRONT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait "$BACK_PID" "$FRONT_PID"
