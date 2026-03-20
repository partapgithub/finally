# Usage: .\scripts\start_windows.ps1 [-Build]
# Starts the FinAlly trading platform in Docker.

param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "finally"
$CONTAINER_NAME = "finally-app"
$VOLUME_NAME = "finally-data"
$PORT = "8000"

# Resolve project root (parent of the scripts directory)
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJECT_DIR = Split-Path -Parent $SCRIPT_DIR

# Check Docker is running
try {
    docker info 2>&1 | Out-Null
} catch {
    Write-Error "Docker is not running. Please start Docker Desktop first."
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not running. Please start Docker Desktop first."
    exit 1
}

# Check if .env file exists
$envFile = Join-Path $PROJECT_DIR ".env"
if (-not (Test-Path $envFile)) {
    Write-Warning ".env file not found at $envFile"
    Write-Host "  Copy .env.example to .env and fill in your API keys:"
    Write-Host "  Copy-Item .env.example .env"
    exit 1
}

# Check if container is already running
$running = docker ps --format "{{.Names}}" 2>&1 | Where-Object { $_ -eq $CONTAINER_NAME }
if ($running -and -not $Build) {
    Write-Host "FinAlly is already running at http://localhost:$PORT"
    exit 0
}

# Stop and remove existing container if running (needed for --build or env changes)
if ($running) {
    Write-Host "Stopping existing container..."
    docker stop $CONTAINER_NAME | Out-Null
    docker rm $CONTAINER_NAME | Out-Null
}

# Remove stopped container with same name if it exists
$stopped = docker ps -a --format "{{.Names}}" 2>&1 | Where-Object { $_ -eq $CONTAINER_NAME }
if ($stopped) {
    Write-Host "Removing stopped container..."
    docker rm $CONTAINER_NAME | Out-Null
}

# Build if image doesn't exist or -Build flag passed
$imageExists = docker images --format "{{.Repository}}" 2>&1 | Where-Object { $_ -eq $IMAGE_NAME }
if ($Build -or -not $imageExists) {
    Write-Host "Building FinAlly image (this may take a few minutes on first run)..."
    docker build -t $IMAGE_NAME $PROJECT_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed."
        exit 1
    }
}

# Start container
Write-Host "Starting FinAlly..."
docker run -d `
    --name $CONTAINER_NAME `
    -p "${PORT}:8000" `
    -v "${VOLUME_NAME}:/app/db" `
    --env-file $envFile `
    --restart unless-stopped `
    $IMAGE_NAME

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start container."
    exit 1
}

Write-Host ""
Write-Host "FinAlly is running at http://localhost:$PORT"
Write-Host "  To stop: .\scripts\stop_windows.ps1"
Write-Host "  To rebuild: .\scripts\start_windows.ps1 -Build"

# Open browser
Start-Sleep -Seconds 2
Start-Process "http://localhost:$PORT"
