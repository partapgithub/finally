"""Health check endpoint."""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def get_health():
    """Return service health status."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
