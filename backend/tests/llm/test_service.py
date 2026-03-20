"""Unit tests for the LLM chat service (app/llm/service.py)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_price_cache(prices: dict[str, float]) -> MagicMock:
    """Build a mock PriceCache with .get() returning PriceUpdate-like objects."""
    cache = MagicMock()

    def _get(ticker: str):
        price = prices.get(ticker)
        if price is None:
            return None
        update = SimpleNamespace(
            ticker=ticker,
            price=price,
            previous_price=price,
            change_percent=0.0,
            direction="flat",
        )
        return update

    cache.get.side_effect = _get
    return cache


# ---------------------------------------------------------------------------
# Mock mode
# ---------------------------------------------------------------------------

class TestMockMode:
    def test_mock_mode_returns_correct_structure(self, monkeypatch):
        """When LLM_MOCK=true, process_chat_message returns MOCK_RESPONSE."""
        monkeypatch.setenv("LLM_MOCK", "true")

        import importlib
        import app.llm.service as svc
        importlib.reload(svc)

        result = svc.process_chat_message("Hello")
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0
        assert "trades_executed" in result
        assert result["trades_executed"] == []
        assert "watchlist_changes_made" in result
        assert result["watchlist_changes_made"] == []
        assert "errors" in result
        assert result["errors"] == []

    def test_mock_mode_case_insensitive(self, monkeypatch):
        """LLM_MOCK=True (capital T) should also trigger mock mode."""
        monkeypatch.setenv("LLM_MOCK", "True")

        import importlib
        import app.llm.service as svc
        importlib.reload(svc)

        result = svc.process_chat_message("Hello")
        assert result["trades_executed"] == []
        assert result["watchlist_changes_made"] == []

    def test_mock_mode_not_triggered_when_false(self, monkeypatch):
        """LLM_MOCK=false should NOT trigger mock mode (LLM call attempted)."""
        monkeypatch.setenv("LLM_MOCK", "false")

        import importlib
        import app.llm.service as svc
        importlib.reload(svc)

        price_cache = _make_price_cache({})

        with (
            patch.object(svc, "_call_llm", return_value={"message": "Live response"}),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("Hello")

        assert result["message"] == "Live response"


# ---------------------------------------------------------------------------
# process_chat_message with mocked dependencies
# ---------------------------------------------------------------------------

class TestProcessChatMessage:
    def _get_svc(self, monkeypatch):
        """Reload service with LLM_MOCK disabled and return the module."""
        monkeypatch.delenv("LLM_MOCK", raising=False)
        import importlib
        import app.llm.service as svc
        importlib.reload(svc)
        return svc

    def test_basic_response_structure(self, monkeypatch):
        """process_chat_message returns the expected top-level keys."""
        svc = self._get_svc(monkeypatch)
        price_cache = _make_price_cache({})

        with (
            patch.object(svc, "_call_llm", return_value={"message": "Looking good!"}),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("How's my portfolio?")

        assert result["message"] == "Looking good!"
        assert isinstance(result["trades_executed"], list)
        assert isinstance(result["watchlist_changes_made"], list)
        assert isinstance(result["errors"], list)

    def test_trade_auto_execution_success(self, monkeypatch):
        """Trades in the LLM response are auto-executed via execute_trade."""
        svc = self._get_svc(monkeypatch)
        price_cache = _make_price_cache({"AAPL": 195.0})

        mock_execute = MagicMock(
            return_value={"success": True, "error": None, "trade_id": "t1"}
        )

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Buying 5 AAPL for you.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "execute_trade", mock_execute),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("Buy 5 AAPL")

        assert len(result["trades_executed"]) == 1
        trade = result["trades_executed"][0]
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 5
        assert trade["price"] == 195.0
        assert trade["success"] is True
        assert trade["error"] is None

    def test_trade_fails_insufficient_cash(self, monkeypatch):
        """Failed trades (e.g., insufficient cash) are recorded with success=False."""
        svc = self._get_svc(monkeypatch)
        price_cache = _make_price_cache({"AAPL": 195.0})

        mock_execute = MagicMock(
            return_value={
                "success": False,
                "error": "Insufficient cash: need $195000.00, have $10000.00",
                "trade_id": None,
            }
        )

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Buying 1000 AAPL.",
                "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1000}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "execute_trade", mock_execute),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("Buy 1000 AAPL")

        assert result["trades_executed"][0]["success"] is False
        assert "Insufficient cash" in result["trades_executed"][0]["error"]
        assert len(result["errors"]) > 0

    def test_trade_skipped_no_price(self, monkeypatch):
        """Trades for tickers with no cached price are skipped gracefully."""
        svc = self._get_svc(monkeypatch)
        # Empty price cache -- UNKN has no price
        price_cache = _make_price_cache({})

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Buying UNKN.",
                "trades": [{"ticker": "UNKN", "side": "buy", "quantity": 1}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("Buy UNKN")

        assert len(result["trades_executed"]) == 1
        assert result["trades_executed"][0]["success"] is False
        assert "No price available" in result["trades_executed"][0]["error"]

    def test_watchlist_add(self, monkeypatch):
        """Watchlist changes with action='add' call add_to_watchlist."""
        svc = self._get_svc(monkeypatch)
        mock_add = MagicMock(return_value={"success": True, "error": None})

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Added PYPL to your watchlist.",
                "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "add_to_watchlist", mock_add),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Watch PYPL")

        assert len(result["watchlist_changes_made"]) == 1
        change = result["watchlist_changes_made"][0]
        assert change["ticker"] == "PYPL"
        assert change["action"] == "add"
        assert change["success"] is True
        mock_add.assert_called_once_with("default", "PYPL")

    def test_watchlist_remove(self, monkeypatch):
        """Watchlist changes with action='remove' call remove_from_watchlist."""
        svc = self._get_svc(monkeypatch)
        mock_remove = MagicMock(return_value={"success": True})

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Removed TSLA from your watchlist.",
                "watchlist_changes": [{"ticker": "TSLA", "action": "remove"}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "remove_from_watchlist", mock_remove),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Remove TSLA from watchlist")

        assert result["watchlist_changes_made"][0]["action"] == "remove"
        assert result["watchlist_changes_made"][0]["success"] is True
        mock_remove.assert_called_once_with("default", "TSLA")

    def test_invalid_json_from_llm(self, monkeypatch):
        """If _call_llm raises JSONDecodeError, return an error message without crashing."""
        svc = self._get_svc(monkeypatch)

        with (
            patch.object(
                svc, "_call_llm",
                side_effect=json.JSONDecodeError("Expecting value", "", 0),
            ),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Hello")

        assert "error" in result["message"].lower()
        assert len(result["errors"]) > 0
        assert result["trades_executed"] == []
        assert result["watchlist_changes_made"] == []

    def test_llm_connection_error(self, monkeypatch):
        """If _call_llm raises a generic exception, return an error message without crashing."""
        svc = self._get_svc(monkeypatch)

        with (
            patch.object(
                svc, "_call_llm",
                side_effect=RuntimeError("Connection refused"),
            ),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Hello")

        assert "error" in result["message"].lower()
        assert len(result["errors"]) > 0
        assert result["trades_executed"] == []

    def test_missing_message_key_uses_fallback(self, monkeypatch):
        """If LLM JSON lacks 'message', fallback text is used."""
        svc = self._get_svc(monkeypatch)

        # LLM returns dict without 'message' key
        with (
            patch.object(svc, "_call_llm", return_value={"trades": [], "watchlist_changes": []}),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Hello")

        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0

    def test_ticker_normalized_to_uppercase(self, monkeypatch):
        """Tickers from the LLM response are uppercased before trade/watchlist calls."""
        svc = self._get_svc(monkeypatch)
        price_cache = _make_price_cache({"AAPL": 200.0})
        mock_execute = MagicMock(
            return_value={"success": True, "error": None, "trade_id": "t1"}
        )

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Buying aapl.",
                "trades": [{"ticker": "aapl", "side": "buy", "quantity": 1}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "execute_trade", mock_execute),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            result = svc.process_chat_message("Buy aapl")

        # execute_trade should be called with uppercased ticker
        call_args = mock_execute.call_args
        assert call_args[0][1] == "AAPL"

    def test_malformed_trade_entry_skipped(self, monkeypatch):
        """A trade entry with an empty ticker is skipped and logged as an error."""
        svc = self._get_svc(monkeypatch)

        with (
            patch.object(svc, "_call_llm", return_value={
                "message": "Processing.",
                "trades": [{"ticker": "", "side": "buy", "quantity": 1}],
            }),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=[]),
            patch.object(svc, "_get_price_cache", return_value=_make_price_cache({})),
        ):
            result = svc.process_chat_message("Do something")

        assert result["trades_executed"] == []
        assert len(result["errors"]) > 0

    def test_chat_history_included_in_messages(self, monkeypatch):
        """Historical messages are passed to _call_llm in the messages array."""
        svc = self._get_svc(monkeypatch)
        price_cache = _make_price_cache({})

        history = [
            {"role": "user", "content": "Prior question", "actions": None, "created_at": "ts1"},
            {"role": "assistant", "content": "Prior answer", "actions": None, "created_at": "ts2"},
        ]

        captured_messages = []

        def capture_llm(messages):
            captured_messages.extend(messages)
            return {"message": "OK"}

        with (
            patch.object(svc, "_call_llm", side_effect=capture_llm),
            patch.object(svc, "_build_portfolio_context", return_value="ctx"),
            patch.object(svc, "get_chat_history", return_value=history),
            patch.object(svc, "_get_price_cache", return_value=price_cache),
        ):
            svc.process_chat_message("New question")

        roles = [m["role"] for m in captured_messages]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles
        # The new user message is always last
        assert captured_messages[-1]["role"] == "user"
        assert "New question" in captured_messages[-1]["content"]
