#!/usr/bin/env bash
set -euo pipefail

# Always resolve paths from this script location so it works from any cwd.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd -- "${BACKEND_DIR}/.." && pwd)"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-1}"

cd "${BACKEND_DIR}"

PY_BIN="${PY_BIN:-}"
if [[ -z "${PY_BIN}" ]]; then
  if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
    PY_BIN="${PROJECT_ROOT}/.venv/bin/python"
  elif [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
    PY_BIN="${BACKEND_DIR}/.venv/bin/python"
  elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  else
    PY_BIN="python3"
  fi
fi

if [[ "${RELOAD}" == "1" ]]; then
  exec "${PY_BIN}" -m uvicorn app.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --reload \
    --app-dir "${BACKEND_DIR}" \
    --reload-dir "${BACKEND_DIR}"
else
  exec "${PY_BIN}" -m uvicorn app.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --app-dir "${BACKEND_DIR}"
fi
