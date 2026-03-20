"""Unit tests for PriceCache (cache.py)."""

import threading

from app.market.cache import PriceCache


class TestPriceCacheUpdateAndGet:
    def test_update_returns_price_update(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.ticker == "AAPL"
        assert update.price == 190.50

    def test_get_returns_stored_update(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert cache.get("AAPL") == update

    def test_get_unknown_ticker_returns_none(self):
        cache = PriceCache()
        assert cache.get("ZZZZ") is None

    def test_get_price_convenience(self):
        cache = PriceCache()
        cache.update("AAPL", 190.50)
        assert cache.get_price("AAPL") == 190.50

    def test_get_price_unknown_returns_none(self):
        cache = PriceCache()
        assert cache.get_price("NOPE") is None

    def test_price_rounded_to_two_decimals(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.123456)
        assert update.price == round(190.123456, 2)


class TestPriceCacheDirection:
    def test_first_update_is_flat(self):
        cache = PriceCache()
        update = cache.update("AAPL", 190.50)
        assert update.direction == "flat"
        assert update.previous_price == 190.50

    def test_second_update_up(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 191.00)
        assert update.direction == "up"
        assert update.previous_price == 190.00
        assert update.change == 1.00

    def test_second_update_down(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        update = cache.update("AAPL", 189.00)
        assert update.direction == "down"
        assert update.change == -1.00


class TestPriceCacheRemoveAndGetAll:
    def test_remove_ticker(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.remove("AAPL")
        assert cache.get("AAPL") is None

    def test_remove_nonexistent_is_noop(self):
        cache = PriceCache()
        cache.remove("NOPE")  # Should not raise

    def test_get_all_returns_all_tickers(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        cache.update("GOOGL", 175.00)
        all_prices = cache.get_all()
        assert set(all_prices.keys()) == {"AAPL", "GOOGL"}

    def test_get_all_is_shallow_copy(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        snapshot = cache.get_all()
        cache.update("AAPL", 191.00)  # Should not affect snapshot
        assert snapshot["AAPL"].price == 190.00


class TestPriceCacheVersionAndContains:
    def test_version_increments_on_update(self):
        cache = PriceCache()
        v0 = cache.version
        cache.update("AAPL", 190.00)
        assert cache.version == v0 + 1
        cache.update("AAPL", 191.00)
        assert cache.version == v0 + 2

    def test_version_does_not_increment_on_remove(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        v = cache.version
        cache.remove("AAPL")
        assert cache.version == v

    def test_len(self):
        cache = PriceCache()
        assert len(cache) == 0
        cache.update("AAPL", 190.00)
        assert len(cache) == 1
        cache.update("GOOGL", 175.00)
        assert len(cache) == 2

    def test_contains(self):
        cache = PriceCache()
        cache.update("AAPL", 190.00)
        assert "AAPL" in cache
        assert "NOPE" not in cache


class TestPriceCacheThreadSafety:
    def test_concurrent_writes_do_not_corrupt(self):
        """Multiple threads writing simultaneously must not corrupt the cache."""
        cache = PriceCache()
        errors: list[Exception] = []

        def writer(ticker: str, price: float) -> None:
            try:
                for i in range(100):
                    cache.update(ticker, price + i)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=("AAPL", 100.0)),
            threading.Thread(target=writer, args=("GOOGL", 200.0)),
            threading.Thread(target=writer, args=("MSFT", 300.0)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # After all writes, each ticker should still have a valid price
        for ticker in ("AAPL", "GOOGL", "MSFT"):
            assert cache.get(ticker) is not None
