"""Integration tests for SimulatorDataSource (simulator.py)."""

import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource


class TestSimulatorDataSourceStartStop:
    async def test_start_populates_cache_immediately(self):
        """Cache should have seed prices before the first loop tick."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL", "GOOGL"])

        assert cache.get("AAPL") is not None
        assert cache.get("GOOGL") is not None

        await source.stop()

    async def test_stop_is_clean(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.stop()

    async def test_double_stop_does_not_raise(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start(["AAPL"])
        await source.stop()
        await source.stop()  # Second stop should be a no-op

    async def test_prices_update_over_time(self):
        """Cache version should increase as the simulator produces updates."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.05)
        await source.start(["AAPL"])

        v0 = cache.version
        await asyncio.sleep(0.2)  # Allow several update cycles
        assert cache.version > v0

        await source.stop()

    async def test_get_tickers_before_start(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache)
        assert source.get_tickers() == []

    async def test_get_tickers_after_start(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL", "GOOGL"])
        assert set(source.get_tickers()) == {"AAPL", "GOOGL"}
        await source.stop()


class TestSimulatorDataSourceAddRemove:
    async def test_add_ticker_seeds_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL"])

        await source.add_ticker("TSLA")
        assert "TSLA" in source.get_tickers()
        assert cache.get("TSLA") is not None

        await source.stop()

    async def test_remove_ticker_clears_cache(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL", "TSLA"])

        await source.remove_ticker("TSLA")
        assert "TSLA" not in source.get_tickers()
        assert cache.get("TSLA") is None

        await source.stop()

    async def test_add_then_remove_ticker(self):
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=10.0)
        await source.start(["AAPL"])

        await source.add_ticker("NVDA")
        assert "NVDA" in source.get_tickers()

        await source.remove_ticker("NVDA")
        assert "NVDA" not in source.get_tickers()
        assert cache.get("NVDA") is None

        await source.stop()

    async def test_empty_start(self):
        """Starting with no tickers should not raise."""
        cache = PriceCache()
        source = SimulatorDataSource(price_cache=cache, update_interval=0.1)
        await source.start([])
        assert source.get_tickers() == []
        await asyncio.sleep(0.15)  # One tick should not crash
        await source.stop()
