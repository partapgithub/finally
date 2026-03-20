"""Unit tests for GBMSimulator (simulator.py)."""

from app.market.seed_prices import SEED_PRICES
from app.market.simulator import GBMSimulator


class TestGBMSimulatorInit:
    def test_initial_prices_match_seeds(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]

    def test_all_default_tickers_have_seed_prices(self):
        tickers = list(SEED_PRICES.keys())
        sim = GBMSimulator(tickers=tickers)
        for ticker in tickers:
            assert sim.get_price(ticker) == SEED_PRICES[ticker]

    def test_unknown_ticker_gets_random_seed_price(self):
        sim = GBMSimulator(tickers=["ZZZZ"])
        price = sim.get_price("ZZZZ")
        assert price is not None
        assert 50.0 <= price <= 300.0

    def test_empty_tickers_list(self):
        sim = GBMSimulator(tickers=[])
        assert sim.get_tickers() == []


class TestGBMSimulatorStep:
    def test_step_returns_all_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        result = sim.step()
        assert set(result.keys()) == {"AAPL", "GOOGL"}

    def test_empty_step_returns_empty_dict(self):
        sim = GBMSimulator(tickers=[])
        assert sim.step() == {}

    def test_prices_are_always_positive(self):
        """GBM prices can never go negative (exp() is always > 0)."""
        sim = GBMSimulator(tickers=["AAPL", "TSLA"])
        for _ in range(1000):
            prices = sim.step()
            for price in prices.values():
                assert price > 0

    def test_prices_change_over_time(self):
        """After many steps, prices should have drifted from their seeds."""
        sim = GBMSimulator(tickers=["AAPL"])
        initial = sim.get_price("AAPL")
        for _ in range(500):
            sim.step()
        assert sim.get_price("AAPL") != initial

    def test_prices_rounded_to_two_decimals(self):
        sim = GBMSimulator(tickers=["AAPL"])
        result = sim.step()
        price = result["AAPL"]
        assert price == round(price, 2)

    def test_full_default_watchlist_step(self):
        """Cholesky decomposition succeeds for all 10 default tickers."""
        tickers = list(SEED_PRICES.keys())
        sim = GBMSimulator(tickers=tickers)
        result = sim.step()
        assert set(result.keys()) == set(tickers)


class TestGBMSimulatorAddRemove:
    def test_add_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("TSLA")
        result = sim.step()
        assert "TSLA" in result

    def test_add_duplicate_is_noop(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.add_ticker("AAPL")
        assert sim.get_tickers().count("AAPL") == 1

    def test_remove_ticker(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        sim.remove_ticker("GOOGL")
        result = sim.step()
        assert "GOOGL" not in result
        assert "AAPL" in result

    def test_remove_nonexistent_is_noop(self):
        sim = GBMSimulator(tickers=["AAPL"])
        sim.remove_ticker("NOPE")  # Should not raise

    def test_get_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        assert set(sim.get_tickers()) == {"AAPL", "GOOGL"}

    def test_get_price_returns_none_for_unknown(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim.get_price("NOPE") is None


class TestGBMSimulatorCholesky:
    def test_cholesky_none_for_single_ticker(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None  # No correlation matrix needed for 1 ticker

    def test_cholesky_built_for_multiple_tickers(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL"])
        assert sim._cholesky is not None

    def test_cholesky_rebuilds_on_add(self):
        sim = GBMSimulator(tickers=["AAPL"])
        assert sim._cholesky is None
        sim.add_ticker("GOOGL")
        assert sim._cholesky is not None

    def test_cholesky_rebuilds_on_remove(self):
        sim = GBMSimulator(tickers=["AAPL", "GOOGL", "MSFT"])
        assert sim._cholesky is not None
        sim.remove_ticker("GOOGL")
        sim.remove_ticker("MSFT")
        assert sim._cholesky is None  # Back to 1 ticker


class TestGBMSimulatorCorrelation:
    def test_tsla_gets_lower_correlation(self):
        from app.market.simulator import GBMSimulator
        rho = GBMSimulator._pairwise_correlation("TSLA", "AAPL")
        assert rho == 0.3  # TSLA_CORR

    def test_tsla_with_tsla_uses_tsla_corr(self):
        rho = GBMSimulator._pairwise_correlation("TSLA", "TSLA")
        assert rho == 0.3

    def test_tech_tech_correlation(self):
        rho = GBMSimulator._pairwise_correlation("AAPL", "MSFT")
        assert rho == 0.6  # INTRA_TECH_CORR

    def test_finance_finance_correlation(self):
        rho = GBMSimulator._pairwise_correlation("JPM", "V")
        assert rho == 0.5  # INTRA_FINANCE_CORR

    def test_cross_sector_correlation(self):
        rho = GBMSimulator._pairwise_correlation("AAPL", "JPM")
        assert rho == 0.3  # CROSS_GROUP_CORR

    def test_unknown_ticker_correlation(self):
        rho = GBMSimulator._pairwise_correlation("ZZZZ", "AAPL")
        assert rho == 0.3  # CROSS_GROUP_CORR
