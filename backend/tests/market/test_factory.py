"""Unit tests for create_market_data_source factory (factory.py)."""

import os
from unittest.mock import patch

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


class TestCreateMarketDataSource:
    def test_returns_simulator_when_no_api_key(self):
        cache = PriceCache()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MASSIVE_API_KEY", None)
            source = create_market_data_source(cache)
        assert isinstance(source, SimulatorDataSource)

    def test_returns_simulator_when_api_key_empty(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
            source = create_market_data_source(cache)
        assert isinstance(source, SimulatorDataSource)

    def test_returns_simulator_when_api_key_whitespace(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
            source = create_market_data_source(cache)
        assert isinstance(source, SimulatorDataSource)

    def test_returns_massive_when_api_key_set(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-api-key-12345"}):
            source = create_market_data_source(cache)
        assert isinstance(source, MassiveDataSource)

    def test_massive_source_uses_provided_api_key(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "my-secret-key"}):
            source = create_market_data_source(cache)
        assert isinstance(source, MassiveDataSource)
        assert source._api_key == "my-secret-key"

    def test_simulator_source_uses_provided_cache(self):
        cache = PriceCache()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MASSIVE_API_KEY", None)
            source = create_market_data_source(cache)
        assert isinstance(source, SimulatorDataSource)
        assert source._cache is cache

    def test_massive_source_uses_provided_cache(self):
        cache = PriceCache()
        with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}):
            source = create_market_data_source(cache)
        assert isinstance(source, MassiveDataSource)
        assert source._cache is cache
