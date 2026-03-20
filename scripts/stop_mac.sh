#!/usr/bin/env bash
# Usage: ./scripts/stop_mac.sh
# Note: Make this script executable with: chmod +x scripts/stop_mac.sh
CONTAINER_NAME="finally-app"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Stopping FinAlly..."
  docker stop "${CONTAINER_NAME}"
  docker rm "${CONTAINER_NAME}"
  echo "FinAlly stopped. Your data is preserved in the Docker volume."
  echo "  To remove data permanently: docker volume rm finally-data"
else
  echo "FinAlly is not running."
fi
