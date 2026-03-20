#!/usr/bin/env bash
# Usage: ./scripts/start_mac.sh [--build]
# Note: Make this script executable with: chmod +x scripts/start_mac.sh
set -e

IMAGE_NAME="finally"
CONTAINER_NAME="finally-app"
VOLUME_NAME="finally-data"
PORT="8000"

# Resolve script and project directories regardless of where the script is called from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Parse flags
FORCE_BUILD=false
for arg in "$@"; do
  case $arg in
    --build) FORCE_BUILD=true ;;
  esac
done

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop first."
  exit 1
fi

# Check if .env file exists
if [ ! -f "${PROJECT_DIR}/.env" ]; then
  echo "Warning: .env file not found at ${PROJECT_DIR}/.env"
  echo "  Copy .env.example to .env and fill in your API keys:"
  echo "  cp .env.example .env"
  exit 1
fi

# Check if container is already running
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "FinAlly is already running at http://localhost:${PORT}"
  exit 0
fi

# Remove stopped container with same name if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Removing stopped container..."
  docker rm "${CONTAINER_NAME}"
fi

# Build if image doesn't exist or --build flag passed
if [ "$FORCE_BUILD" = true ] || ! docker images --format '{{.Repository}}' | grep -q "^${IMAGE_NAME}$"; then
  echo "Building FinAlly image (this may take a few minutes on first run)..."
  docker build -t "${IMAGE_NAME}" "${PROJECT_DIR}"
fi

# Start container
echo "Starting FinAlly..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8000" \
  -v "${VOLUME_NAME}:/app/db" \
  --env-file "${PROJECT_DIR}/.env" \
  --restart unless-stopped \
  "${IMAGE_NAME}"

echo ""
echo "FinAlly is running at http://localhost:${PORT}"
echo "  To stop: ./scripts/stop_mac.sh"
echo "  To rebuild: ./scripts/start_mac.sh --build"

# Open browser if 'open' command is available (macOS)
if command -v open > /dev/null 2>&1; then
  sleep 2
  open "http://localhost:${PORT}"
fi
