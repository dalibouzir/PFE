#!/bin/sh
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
fi

if [ "${RUN_SEED_DATA:-0}" = "1" ]; then
  python3 -m app.seeds.seed_data
fi

if [ "${RUN_ML_TRAINING:-0}" = "1" ]; then
  if ! python3 -m app.ml.training.runner; then
    echo "ML training skipped at startup due to runtime configuration"
  fi
fi

exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers "${UVICORN_WORKERS:-1}"
