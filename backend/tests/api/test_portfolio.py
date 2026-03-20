"""Unit tests for the portfolio API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.market.models import PriceUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_update(ticker: str, price: float, previous_price: float | None = None) -> PriceUpdate:
    pp = previous_price if previous_price is not None else price
    return PriceUpdate(ticker=ticker, price=price, previous_price=pp)


def _build_app(mock_cache, mock_portfolio, mock_history, mock_execute):
    """Build a minimal FastAPI app with portfolio routes and mocked dependencies."""
    from app.api.portfolio import router

    app = FastAPI()

    # Patch app.main getters used by route handlers
    with patch("app.main.get_price_cache", return_value=mock_cache):
        with patch("app.main.get_market_source", return_value=MagicMock()):
            pass  # patches are for import time — use app-level overrides instead

    app.include_router(router, prefix="/api")
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_cache():
    cache = MagicMock()
    cache.get.side_effect = lambda ticker: _make_price_update(ticker, 200.0, 195.0)
    return cache


@pytest.fixture()
def mock_portfolio():
    return {
        "cash_balance": 8000.0,
        "positions": [
            {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.0},
        ],
        "total_value": 8000.0,
    }


@pytest.fixture()
def client(mock_cache, mock_portfolio):
    from app.api.portfolio import router

    app = FastAPI()
    app.include_router(router, prefix="/api")

    with (
        patch("app.api.portfolio.get_portfolio", return_value=mock_portfolio),
        patch("app.api.portfolio.get_portfolio_history", return_value=[]),
        patch("app.api.portfolio.execute_trade", return_value={"success": True, "trade_id": "abc", "error": None}),
        patch("app.main.get_price_cache", return_value=mock_cache),
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------


class TestGetPortfolio:
    def test_returns_200(self, client):
        response = client.get("/api/portfolio")
        assert response.status_code == 200

    def test_response_shape(self, client):
        response = client.get("/api/portfolio")
        data = response.json()
        assert "cash_balance" in data
        assert "positions" in data
        assert "total_value" in data

    def test_positions_enriched_with_live_price(self, client):
        response = client.get("/api/portfolio")
        data = response.json()
        pos = data["positions"][0]
        assert "current_price" in pos
        assert "unrealized_pnl" in pos
        assert "pnl_pct" in pos

    def test_total_value_includes_positions(self, client):
        response = client.get("/api/portfolio")
        data = response.json()
        # total_value = cash_balance + (current_price * quantity)
        # cash = 8000, current_price = 200, qty = 10 → total = 10000
        assert data["total_value"] == pytest.approx(10000.0, rel=1e-4)

    def test_unrealized_pnl_calculation(self, client):
        response = client.get("/api/portfolio")
        pos = response.json()["positions"][0]
        # (200 - 190) * 10 = 100
        assert pos["unrealized_pnl"] == pytest.approx(100.0, rel=1e-4)
        # (200 - 190) / 190 * 100 ≈ 5.2632
        assert pos["pnl_pct"] == pytest.approx(5.2632, rel=1e-3)

    def test_no_cache_falls_back_to_avg_cost(self, mock_portfolio):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.portfolio.get_portfolio", return_value=mock_portfolio),
            patch("app.main.get_price_cache", return_value=None),
        ):
            c = TestClient(app)
            response = c.get("/api/portfolio")
        assert response.status_code == 200
        pos = response.json()["positions"][0]
        assert pos["unrealized_pnl"] == 0.0


# ---------------------------------------------------------------------------
# POST /portfolio/trade
# ---------------------------------------------------------------------------


class TestTrade:
    def test_buy_returns_200(self, mock_cache, mock_portfolio):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.portfolio.execute_trade", return_value={"success": True, "trade_id": "t1", "error": None}),
            patch("app.main.get_price_cache", return_value=mock_cache),
        ):
            c = TestClient(app)
            response = c.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["trade_id"] == "t1"
        assert data["price"] == 200.0

    def test_ticker_not_in_cache_returns_400(self, mock_portfolio):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        cache = MagicMock()
        cache.get.return_value = None  # ticker not in cache

        with patch("app.main.get_price_cache", return_value=cache):
            c = TestClient(app)
            response = c.post("/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"})

        assert response.status_code == 400

    def test_insufficient_cash_returns_400(self, mock_cache):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch(
                "app.api.portfolio.execute_trade",
                return_value={"success": False, "trade_id": None, "error": "Insufficient cash"},
            ),
            patch("app.main.get_price_cache", return_value=mock_cache),
        ):
            c = TestClient(app)
            response = c.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10000, "side": "buy"})

        assert response.status_code == 400
        assert "Insufficient cash" in response.json()["detail"]

    def test_invalid_side_returns_422(self, mock_cache):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with patch("app.main.get_price_cache", return_value=mock_cache):
            c = TestClient(app)
            response = c.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"})

        assert response.status_code == 422

    def test_zero_quantity_returns_422(self, mock_cache):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with patch("app.main.get_price_cache", return_value=mock_cache):
            c = TestClient(app)
            response = c.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"})

        assert response.status_code == 422

    def test_ticker_uppercased(self, mock_cache):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch(
                "app.api.portfolio.execute_trade",
                return_value={"success": True, "trade_id": "t2", "error": None},
            ) as mock_exec,
            patch("app.main.get_price_cache", return_value=mock_cache),
        ):
            c = TestClient(app)
            c.post("/api/portfolio/trade", json={"ticker": "aapl", "quantity": 1, "side": "buy"})
            call_args = mock_exec.call_args
            assert call_args.kwargs["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# GET /portfolio/history
# ---------------------------------------------------------------------------


class TestPortfolioHistory:
    def test_returns_list(self, mock_cache, mock_portfolio):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        history = [
            {"total_value": 10000.0, "recorded_at": "2026-03-20T00:00:00"},
            {"total_value": 10100.0, "recorded_at": "2026-03-20T00:00:30"},
        ]
        with (
            patch("app.api.portfolio.get_portfolio_history", return_value=history),
            patch("app.main.get_price_cache", return_value=mock_cache),
        ):
            c = TestClient(app)
            response = c.get("/api/portfolio/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["total_value"] == 10000.0

    def test_empty_history(self, mock_cache):
        from app.api.portfolio import router

        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.portfolio.get_portfolio_history", return_value=[]),
            patch("app.main.get_price_cache", return_value=mock_cache),
        ):
            c = TestClient(app)
            response = c.get("/api/portfolio/history")

        assert response.status_code == 200
        assert response.json() == []
