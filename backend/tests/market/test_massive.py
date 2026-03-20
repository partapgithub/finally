"""Unit tests for MassiveDataSource (massive_client.py).

All tests mock the Massive REST client to avoid real API calls.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.market.cache import PriceCache
from app.market.massive_client import MassiveDataSource


def _make_snapshot(ticker: str, price: float, timestamp_ms: int = 1707580800000) -> MagicMock:
    """Create a mock Massive snapshot object."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade.price = price
    snap.last_trade.timestamp = timestamp_ms
    return snap


class TestMassiveDataSourcePollOnce:
    async def test_poll_updates_cache(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL", "GOOGL"]

        mock_snapshots = [
            _make_snapshot("AAPL", 190.50),
            _make_snapshot("GOOGL", 175.25),
        ]
        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("GOOGL") == 175.25

    async def test_timestamp_conversion_from_ms_to_seconds(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL"]

        ts_ms = 1707580800000
        mock_snapshots = [_make_snapshot("AAPL", 190.50, timestamp_ms=ts_ms)]

        with patch.object(source, "_fetch_snapshots", return_value=mock_snapshots):
            await source._poll_once()

        update = cache.get("AAPL")
        assert update is not None
        # Timestamp should be in seconds, not milliseconds
        assert update.timestamp == ts_ms / 1000.0

    async def test_malformed_snapshot_skipped(self):
        """A snapshot with missing last_trade should be skipped; others processed."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL", "BAD"]

        good_snap = _make_snapshot("AAPL", 190.50)
        bad_snap = MagicMock()
        bad_snap.ticker = "BAD"
        bad_snap.last_trade = None  # Will cause AttributeError

        with patch.object(source, "_fetch_snapshots", return_value=[good_snap, bad_snap]):
            await source._poll_once()

        assert cache.get_price("AAPL") == 190.50
        assert cache.get_price("BAD") is None

    async def test_api_error_does_not_crash(self):
        """A poll failure should be swallowed, not propagated."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = ["AAPL"]

        with patch.object(source, "_fetch_snapshots", side_effect=Exception("network error")):
            await source._poll_once()  # Must not raise

        assert cache.get_price("AAPL") is None

    async def test_skips_poll_when_no_tickers(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = MagicMock()
        source._tickers = []

        # _fetch_snapshots should never be called
        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()

    async def test_skips_poll_when_no_client(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)
        source._client = None
        source._tickers = ["AAPL"]

        with patch.object(source, "_fetch_snapshots") as mock_fetch:
            await source._poll_once()
            mock_fetch.assert_not_called()


class TestMassiveDataSourceLifecycle:
    async def test_start_does_immediate_poll(self):
        """start() should populate the cache before returning."""
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        mock_snapshots = [_make_snapshot("AAPL", 190.50)]

        with (
            patch("app.market.massive_client.RESTClient") as mock_client_cls,
            patch.object(source, "_poll_once", new_callable=AsyncMock) as mock_poll,
        ):
            mock_client_cls.return_value = MagicMock()
            await source.start(["AAPL"])
            mock_poll.assert_called_once()

        await source.stop()

    async def test_stop_cancels_background_task(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with (
            patch("app.market.massive_client.RESTClient") as mock_client_cls,
            patch.object(source, "_poll_once", new_callable=AsyncMock),
        ):
            mock_client_cls.return_value = MagicMock()
            await source.start(["AAPL"])
            assert source._task is not None
            assert not source._task.done()

            await source.stop()
            assert source._task is None

    async def test_double_stop_is_safe(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache, poll_interval=60.0)

        with (
            patch("app.market.massive_client.RESTClient") as mock_client_cls,
            patch.object(source, "_poll_once", new_callable=AsyncMock),
        ):
            mock_client_cls.return_value = MagicMock()
            await source.start(["AAPL"])
            await source.stop()
            await source.stop()  # Should not raise


class TestMassiveDataSourceAddRemove:
    def test_add_ticker(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL"]

        # add_ticker is async but safe to test without event loop for state check
        import asyncio
        asyncio.get_event_loop().run_until_complete(source.add_ticker("GOOGL"))
        assert "GOOGL" in source.get_tickers()

    async def test_add_ticker_normalizes_to_uppercase(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = []

        await source.add_ticker("aapl")
        assert "AAPL" in source.get_tickers()

    async def test_add_duplicate_ticker_is_noop(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL"]

        await source.add_ticker("AAPL")
        assert source.get_tickers().count("AAPL") == 1

    async def test_remove_ticker_clears_cache(self):
        cache = PriceCache()
        cache.update("TSLA", 250.00)
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "TSLA"]

        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None

    async def test_remove_nonexistent_ticker_is_noop(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL"]

        await source.remove_ticker("NOPE")  # Should not raise
        assert source.get_tickers() == ["AAPL"]

    def test_get_tickers_returns_copy(self):
        cache = PriceCache()
        source = MassiveDataSource(api_key="test-key", price_cache=cache)
        source._tickers = ["AAPL", "GOOGL"]

        tickers = source.get_tickers()
        tickers.append("MSFT")  # Modifying the returned list should not affect internal state
        assert "MSFT" not in source._tickers
