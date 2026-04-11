#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT_DIR"/{frontend,backend,ai,database,scripts,docker,docs}

if [ ! -d "$ROOT_DIR/backend/.venv" ]; then
  python3 -m venv "$ROOT_DIR/backend/.venv"
fi

source "$ROOT_DIR/backend/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT_DIR/backend/requirements.txt"
deactivate

if [ -f "$ROOT_DIR/frontend/package.json" ]; then
  cd "$ROOT_DIR/frontend"
  npm install
fi

echo "Setup complete."
echo "Next steps:"
echo "1) cp backend/.env.example backend/.env"
echo "2) Start DB (docker compose -f docker/docker-compose.yml up -d db)"
echo "3) Run dev servers with ./scripts/dev.sh"
