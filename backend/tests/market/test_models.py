"""Unit tests for PriceUpdate dataclass (models.py)."""

from app.market.models import PriceUpdate


class TestPriceUpdateDirection:
    def test_direction_up(self):
        update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, timestamp=1.0)
        assert update.direction == "up"

    def test_direction_down(self):
        update = PriceUpdate(ticker="AAPL", price=189.00, previous_price=190.00, timestamp=1.0)
        assert update.direction == "down"

    def test_direction_flat(self):
        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=190.00, timestamp=1.0)
        assert update.direction == "flat"


class TestPriceUpdateChange:
    def test_change_positive(self):
        update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, timestamp=1.0)
        assert update.change == 1.0

    def test_change_negative(self):
        update = PriceUpdate(ticker="AAPL", price=189.00, previous_price=190.00, timestamp=1.0)
        assert update.change == -1.0

    def test_change_zero(self):
        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=190.00, timestamp=1.0)
        assert update.change == 0.0

    def test_change_percent_positive(self):
        update = PriceUpdate(ticker="AAPL", price=200.00, previous_price=100.00, timestamp=1.0)
        assert update.change_percent == 100.0

    def test_change_percent_negative(self):
        update = PriceUpdate(ticker="AAPL", price=90.00, previous_price=100.00, timestamp=1.0)
        assert update.change_percent == -10.0

    def test_change_percent_zero_previous(self):
        """No ZeroDivisionError when previous_price is zero."""
        update = PriceUpdate(ticker="AAPL", price=100.00, previous_price=0.0, timestamp=1.0)
        assert update.change_percent == 0.0


class TestPriceUpdateToDict:
    def test_to_dict_keys(self):
        update = PriceUpdate(ticker="AAPL", price=190.50, previous_price=190.00, timestamp=1.0)
        d = update.to_dict()
        assert set(d.keys()) == {
            "ticker", "price", "previous_price", "timestamp", "change", "change_percent", "direction"
        }

    def test_to_dict_values(self):
        update = PriceUpdate(ticker="AAPL", price=191.00, previous_price=190.00, timestamp=1.0)
        d = update.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["price"] == 191.00
        assert d["previous_price"] == 190.00
        assert d["direction"] == "up"
        assert d["change"] == 1.0


class TestPriceUpdateImmutability:
    def test_frozen(self):
        """PriceUpdate is frozen — attribute assignment raises AttributeError."""
        update = PriceUpdate(ticker="AAPL", price=190.00, previous_price=190.00, timestamp=1.0)
        try:
            update.price = 200.00  # type: ignore[misc]
            assert False, "Should have raised"
        except (AttributeError, TypeError):
            pass  # Expected
