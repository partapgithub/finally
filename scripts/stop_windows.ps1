# Usage: .\scripts\stop_windows.ps1
# Stops the FinAlly trading platform container.

$CONTAINER_NAME = "finally-app"

$running = docker ps --format "{{.Names}}" 2>&1 | Where-Object { $_ -eq $CONTAINER_NAME }
if ($running) {
    Write-Host "Stopping FinAlly..."
    docker stop $CONTAINER_NAME | Out-Null
    docker rm $CONTAINER_NAME | Out-Null
    Write-Host "FinAlly stopped. Your data is preserved in the Docker volume."
    Write-Host "  To remove data permanently: docker volume rm finally-data"
} else {
    Write-Host "FinAlly is not running."
}
