#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"
npm install

echo "Setup complete."
echo "Next steps:"
echo "1) Run dev server with npm run dev (or ./scripts/dev.sh)"
echo "2) Open http://localhost:3001"
