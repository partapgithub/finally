"""Unit tests for the health endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Minimal app fixture — only registers the health router to avoid requiring
# DB / market data initialisation in unit tests.
# ---------------------------------------------------------------------------


def _build_test_app():
    from fastapi import FastAPI
    from app.api.health import router

    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture()
def client():
    return TestClient(_build_test_app())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["timestamp"]  # non-empty string
