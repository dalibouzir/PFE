#!/usr/bin/env bash
set -euo pipefail

IMAGE_TAG="bouzirdali/weefarm-backend:20260427-1852-amd64"
MIGRATION_PATH="/app/alembic/versions/7c9d2e4a1b3f_add_chat_ui_blocks.py"
CONTAINER_APP_NAME="weefarm-backend-app"
RESOURCE_GROUP="NetworkWatcherRG"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "==> Building image from project root context"
docker build --no-cache \
  -f backend/Dockerfile \
  -t "${IMAGE_TAG}" .

echo "==> Verifying migration file exists in image"
docker run --rm --entrypoint sh \
  "${IMAGE_TAG}" \
  -lc "[ -f '${MIGRATION_PATH}' ] && ls -l '${MIGRATION_PATH}'"

echo "==> Pushing image"
docker push "${IMAGE_TAG}"

echo "==> Deploying Azure Container App"
az containerapp update \
  --name "${CONTAINER_APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --image "${IMAGE_TAG}"

echo "==> Streaming Azure logs"
az containerapp logs show \
  --name "${CONTAINER_APP_NAME}" \
  --resource-group "${RESOURCE_GROUP}" \
  --follow
