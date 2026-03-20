"""Unit tests for the watchlist API endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_test_app(tickers, cache, add_result=None, remove_result=None, market_source=None):
    from app.api.watchlist import router

    app = FastAPI()
    app.include_router(router, prefix="/api")

    patches = [
        patch("app.api.watchlist.get_watchlist", return_value=tickers),
        patch("app.main.get_price_cache", return_value=cache),
        patch("app.main.get_market_source", return_value=market_source or _make_mock_source()),
    ]
    if add_result is not None:
        patches.append(patch("app.api.watchlist.add_to_watchlist", return_value=add_result))
    if remove_result is not None:
        patches.append(patch("app.api.watchlist.remove_from_watchlist", return_value=remove_result))

    return app, patches


def _make_mock_source():
    source = MagicMock()
    source.add_ticker = AsyncMock()
    source.remove_ticker = AsyncMock()
    return source


# ---------------------------------------------------------------------------
# GET /watchlist
# ---------------------------------------------------------------------------


class TestGetWatchlist:
    def test_returns_list_with_prices(self):
        cache = MagicMock()
        cache.get.side_effect = lambda t: _make_price_update(t, 192.5, 190.0)

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.get_watchlist", return_value=["AAPL", "GOOGL"]),
            patch("app.main.get_price_cache", return_value=cache),
        ):
            c = TestClient(app)
            response = c.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["ticker"] == "AAPL"
        assert data[0]["price"] == 192.5
        assert data[0]["change"] is not None
        assert data[0]["change_percent"] is not None
        assert data[0]["direction"] in ("up", "down", "flat")

    def test_ticker_not_in_cache_returns_null_fields(self):
        cache = MagicMock()
        cache.get.return_value = None  # no price data

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.get_watchlist", return_value=["ZZZZ"]),
            patch("app.main.get_price_cache", return_value=cache),
        ):
            c = TestClient(app)
            response = c.get("/api/watchlist")

        assert response.status_code == 200
        data = response.json()
        assert data[0]["price"] is None
        assert data[0]["change"] is None

    def test_empty_watchlist(self):
        cache = MagicMock()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.get_watchlist", return_value=[]),
            patch("app.main.get_price_cache", return_value=cache),
        ):
            c = TestClient(app)
            response = c.get("/api/watchlist")

        assert response.status_code == 200
        assert response.json() == []

    def test_no_cache_returns_null_prices(self):
        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.get_watchlist", return_value=["AAPL"]),
            patch("app.main.get_price_cache", return_value=None),
        ):
            c = TestClient(app)
            response = c.get("/api/watchlist")

        assert response.status_code == 200
        assert response.json()[0]["price"] is None


# ---------------------------------------------------------------------------
# POST /watchlist
# ---------------------------------------------------------------------------


class TestAddWatchlist:
    def test_add_ticker_success(self):
        market_source = _make_mock_source()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.add_to_watchlist", return_value={"success": True, "error": None}),
            patch("app.main.get_market_source", return_value=market_source),
        ):
            c = TestClient(app)
            response = c.post("/api/watchlist", json={"ticker": "TSLA"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ticker"] == "TSLA"
        market_source.add_ticker.assert_called_once_with("TSLA")

    def test_ticker_uppercased(self):
        market_source = _make_mock_source()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.add_to_watchlist", return_value={"success": True, "error": None}) as mock_add,
            patch("app.main.get_market_source", return_value=market_source),
        ):
            c = TestClient(app)
            c.post("/api/watchlist", json={"ticker": "tsla"})
            mock_add.assert_called_once_with("default", "TSLA")

    def test_empty_ticker_returns_422(self):
        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        c = TestClient(app)
        response = c.post("/api/watchlist", json={"ticker": "   "})
        assert response.status_code == 422

    def test_db_failure_returns_400(self):
        market_source = _make_mock_source()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch(
                "app.api.watchlist.add_to_watchlist",
                return_value={"success": False, "error": "Already exists"},
            ),
            patch("app.main.get_market_source", return_value=market_source),
        ):
            c = TestClient(app)
            response = c.post("/api/watchlist", json={"ticker": "AAPL"})

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------


class TestRemoveWatchlist:
    def test_remove_ticker_success(self):
        market_source = _make_mock_source()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.remove_from_watchlist", return_value={"success": True}),
            patch("app.main.get_market_source", return_value=market_source),
        ):
            c = TestClient(app)
            response = c.delete("/api/watchlist/AAPL")

        assert response.status_code == 200
        assert response.json()["success"] is True
        market_source.remove_ticker.assert_called_once_with("AAPL")

    def test_ticker_uppercased_on_delete(self):
        market_source = _make_mock_source()

        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.remove_from_watchlist", return_value={"success": True}) as mock_rm,
            patch("app.main.get_market_source", return_value=market_source),
        ):
            c = TestClient(app)
            c.delete("/api/watchlist/aapl")
            mock_rm.assert_called_once_with("default", "AAPL")

    def test_no_market_source_still_succeeds(self):
        from app.api.watchlist import router
        app = FastAPI()
        app.include_router(router, prefix="/api")

        with (
            patch("app.api.watchlist.remove_from_watchlist", return_value={"success": True}),
            patch("app.main.get_market_source", return_value=None),
        ):
            c = TestClient(app)
            response = c.delete("/api/watchlist/AAPL")

        assert response.status_code == 200
