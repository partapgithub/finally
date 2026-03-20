"""Comprehensive unit tests for the database operations layer."""

import os
import tempfile
import unittest
from unittest.mock import patch


def _make_db(tmp_path: str):
    """Patch get_db_path to use tmp_path, then init_db."""
    with patch("app.db.schema.get_db_path", return_value=tmp_path):
        with patch("app.db.operations.get_connection") as mock_conn:
            # We need real connections pointing to tmp_path
            import sqlite3
            from app.db.schema import get_db_path as _orig

            def _real_conn():
                os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
                conn = sqlite3.connect(tmp_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                return conn

            mock_conn.side_effect = _real_conn

            from app.db.schema import init_db

            with patch("app.db.schema.get_db_path", return_value=tmp_path):
                with patch("app.db.schema.get_connection", side_effect=_real_conn):
                    init_db()
            return _real_conn


class TestInitDb(unittest.TestCase):
    """Tests for init_db() schema creation and seeding."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass

    def _get_conn(self):
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        import sqlite3

        def real_conn():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            return conn

        with patch("app.db.schema.get_db_path", return_value=self.db_path):
            with patch("app.db.schema.get_connection", side_effect=real_conn):
                from app.db import init_db

                init_db()

    def test_creates_all_tables(self):
        self._init()
        conn = self._get_conn()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        expected = {
            "users_profile",
            "watchlist",
            "positions",
            "trades",
            "portfolio_snapshots",
            "chat_messages",
        }
        self.assertTrue(expected.issubset(tables), f"Missing tables: {expected - tables}")

    def test_seeds_default_user(self):
        self._init()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT id, cash_balance FROM users_profile WHERE id='default'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["cash_balance"], 10000.0)

    def test_seeds_ten_watchlist_tickers(self):
        self._init()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id='default'"
        ).fetchall()
        conn.close()
        tickers = {r["ticker"] for r in rows}
        expected = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}
        self.assertEqual(tickers, expected)

    def test_init_idempotent_no_duplicate_seed(self):
        """Running init_db twice should not duplicate seed data."""
        self._init()
        self._init()
        conn = self._get_conn()
        count = conn.execute(
            "SELECT COUNT(*) FROM users_profile WHERE id='default'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)


class _BaseDbTest(unittest.TestCase):
    """Base class that sets up a fresh in-memory/temp database for each test."""

    def setUp(self):
        import sqlite3

        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name

        def real_conn():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        self._real_conn = real_conn

        # Patch get_db_path and get_connection everywhere they are used
        self.patcher_schema_path = patch("app.db.schema.get_db_path", return_value=self.db_path)
        self.patcher_schema_conn = patch("app.db.schema.get_connection", side_effect=real_conn)
        self.patcher_ops_conn = patch("app.db.operations.get_connection", side_effect=real_conn)

        self.patcher_schema_path.start()
        self.patcher_schema_conn.start()
        self.patcher_ops_conn.start()

        from app.db import init_db

        init_db()

    def tearDown(self):
        self.patcher_ops_conn.stop()
        self.patcher_schema_conn.stop()
        self.patcher_schema_path.stop()
        try:
            os.unlink(self.db_path)
        except FileNotFoundError:
            pass


class TestExecuteTradeBuy(_BaseDbTest):
    """Tests for execute_trade() buy-side logic."""

    def test_buy_deducts_cash(self):
        from app.db import execute_trade, get_portfolio

        result = execute_trade("default", "AAPL", "buy", 10, 150.0)
        self.assertTrue(result["success"])
        portfolio = get_portfolio("default")
        self.assertAlmostEqual(portfolio["cash_balance"], 10000.0 - 1500.0)

    def test_buy_creates_position(self):
        from app.db import execute_trade, get_portfolio

        execute_trade("default", "AAPL", "buy", 10, 150.0)
        portfolio = get_portfolio("default")
        pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
        self.assertAlmostEqual(pos["quantity"], 10.0)
        self.assertAlmostEqual(pos["avg_cost"], 150.0)

    def test_buy_records_trade(self):
        import sqlite3

        from app.db import execute_trade

        result = execute_trade("default", "AAPL", "buy", 5, 200.0)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM trades WHERE id=?", (result["trade_id"],)
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["ticker"], "AAPL")
        self.assertEqual(row["side"], "buy")
        self.assertAlmostEqual(row["quantity"], 5.0)
        self.assertAlmostEqual(row["price"], 200.0)

    def test_buy_fails_insufficient_cash(self):
        from app.db import execute_trade

        result = execute_trade("default", "AAPL", "buy", 1000, 100.0)  # $100,000 needed
        self.assertFalse(result["success"])
        self.assertIsNotNone(result["error"])
        self.assertIn("Insufficient cash", result["error"])
        self.assertIsNone(result["trade_id"])

    def test_buy_weighted_avg_cost(self):
        from app.db import execute_trade, get_portfolio

        execute_trade("default", "AAPL", "buy", 10, 100.0)  # 10 shares @ $100
        execute_trade("default", "AAPL", "buy", 10, 200.0)  # 10 shares @ $200
        portfolio = get_portfolio("default")
        pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
        self.assertAlmostEqual(pos["quantity"], 20.0)
        self.assertAlmostEqual(pos["avg_cost"], 150.0)  # (1000 + 2000) / 20

    def test_buy_records_portfolio_snapshot(self):
        import sqlite3

        from app.db import execute_trade

        execute_trade("default", "AAPL", "buy", 1, 100.0)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        count = conn.execute(
            "SELECT COUNT(*) FROM portfolio_snapshots WHERE user_id='default'"
        ).fetchone()[0]
        conn.close()
        self.assertGreater(count, 0)


class TestExecuteTradeSell(_BaseDbTest):
    """Tests for execute_trade() sell-side logic."""

    def setUp(self):
        super().setUp()
        # Buy some shares to sell
        from app.db import execute_trade

        execute_trade("default", "AAPL", "buy", 20, 100.0)

    def test_sell_returns_cash(self):
        from app.db import execute_trade, get_portfolio

        cash_before = get_portfolio("default")["cash_balance"]
        execute_trade("default", "AAPL", "sell", 10, 120.0)
        cash_after = get_portfolio("default")["cash_balance"]
        self.assertAlmostEqual(cash_after, cash_before + 10 * 120.0)

    def test_sell_updates_position(self):
        from app.db import execute_trade, get_portfolio

        execute_trade("default", "AAPL", "sell", 5, 100.0)
        portfolio = get_portfolio("default")
        pos = next(p for p in portfolio["positions"] if p["ticker"] == "AAPL")
        self.assertAlmostEqual(pos["quantity"], 15.0)

    def test_sell_deletes_position_when_fully_sold(self):
        from app.db import execute_trade, get_portfolio

        result = execute_trade("default", "AAPL", "sell", 20, 100.0)
        self.assertTrue(result["success"])
        portfolio = get_portfolio("default")
        tickers = [p["ticker"] for p in portfolio["positions"]]
        self.assertNotIn("AAPL", tickers)

    def test_sell_fails_insufficient_quantity(self):
        from app.db import execute_trade

        result = execute_trade("default", "AAPL", "sell", 999, 100.0)
        self.assertFalse(result["success"])
        self.assertIn("Insufficient shares", result["error"])
        self.assertIsNone(result["trade_id"])

    def test_sell_fails_no_position(self):
        from app.db import execute_trade

        result = execute_trade("default", "GOOGL", "sell", 1, 100.0)
        self.assertFalse(result["success"])
        self.assertIsNone(result["trade_id"])


class TestWatchlist(_BaseDbTest):
    """Tests for watchlist operations."""

    def test_get_watchlist_returns_seeded_tickers(self):
        from app.db import get_watchlist

        tickers = get_watchlist("default")
        expected = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}
        self.assertEqual(set(tickers), expected)
        self.assertEqual(len(tickers), 10)

    def test_add_to_watchlist(self):
        from app.db import add_to_watchlist, get_watchlist

        result = add_to_watchlist("default", "PYPL")
        self.assertTrue(result["success"])
        tickers = get_watchlist("default")
        self.assertIn("PYPL", tickers)

    def test_add_duplicate_ticker_returns_error(self):
        """Adding an existing ticker should return success=False with an error message."""
        from app.db import add_to_watchlist, get_watchlist

        result = add_to_watchlist("default", "AAPL")
        self.assertFalse(result["success"])
        self.assertIsNotNone(result.get("error"))
        # Count should not increase
        tickers = get_watchlist("default")
        self.assertEqual(tickers.count("AAPL"), 1)

    def test_remove_from_watchlist(self):
        from app.db import get_watchlist, remove_from_watchlist

        result = remove_from_watchlist("default", "AAPL")
        self.assertTrue(result["success"])
        tickers = get_watchlist("default")
        self.assertNotIn("AAPL", tickers)

    def test_remove_nonexistent_ticker_succeeds(self):
        """Removing a ticker not in the watchlist should not raise."""
        from app.db import remove_from_watchlist

        result = remove_from_watchlist("default", "XYZ")
        self.assertTrue(result["success"])


class TestChatHistory(_BaseDbTest):
    """Tests for chat message storage and retrieval."""

    def test_add_and_get_chat_message(self):
        from app.db import add_chat_message, get_chat_history

        add_chat_message("default", "user", "Hello AI")
        history = get_chat_history("default")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello AI")
        self.assertIsNone(history[0]["actions"])

    def test_add_chat_message_with_actions(self):
        from app.db import add_chat_message, get_chat_history

        actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
        add_chat_message("default", "assistant", "Buying AAPL for you", actions=actions)
        history = get_chat_history("default")
        self.assertIsNotNone(history[0]["actions"])
        self.assertEqual(history[0]["actions"]["trades"][0]["ticker"], "AAPL")

    def test_get_chat_history_returns_last_n_messages(self):
        from app.db import add_chat_message, get_chat_history

        for i in range(15):
            add_chat_message("default", "user", f"Message {i}")

        history = get_chat_history("default", limit=10)
        self.assertEqual(len(history), 10)
        # Should be the last 10 messages in chronological order
        self.assertEqual(history[-1]["content"], "Message 14")
        self.assertEqual(history[0]["content"], "Message 5")

    def test_get_chat_history_default_limit_is_ten(self):
        from app.db import add_chat_message, get_chat_history

        for i in range(12):
            add_chat_message("default", "user", f"Msg {i}")

        history = get_chat_history("default")
        self.assertEqual(len(history), 10)

    def test_chat_history_chronological_order(self):
        from app.db import add_chat_message, get_chat_history

        add_chat_message("default", "user", "First")
        add_chat_message("default", "assistant", "Second")
        history = get_chat_history("default")
        self.assertEqual(history[0]["content"], "First")
        self.assertEqual(history[1]["content"], "Second")


class TestPortfolioSnapshot(_BaseDbTest):
    """Tests for portfolio snapshot recording."""

    def test_record_portfolio_snapshot(self):
        import sqlite3

        from app.db import record_portfolio_snapshot

        record_portfolio_snapshot("default", 12345.67)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id='default'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertAlmostEqual(row["total_value"], 12345.67)

    def test_multiple_snapshots_preserved(self):
        import sqlite3

        from app.db import record_portfolio_snapshot

        record_portfolio_snapshot("default", 10000.0)
        record_portfolio_snapshot("default", 10500.0)
        record_portfolio_snapshot("default", 11000.0)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT total_value FROM portfolio_snapshots WHERE user_id='default' "
            "ORDER BY recorded_at ASC"
        ).fetchall()
        conn.close()
        values = [r["total_value"] for r in rows]
        self.assertIn(10000.0, values)
        self.assertIn(10500.0, values)
        self.assertIn(11000.0, values)

    def test_get_portfolio_history_ordered(self):
        from app.db import get_portfolio_history, record_portfolio_snapshot

        record_portfolio_snapshot("default", 10000.0)
        record_portfolio_snapshot("default", 10500.0)
        history = get_portfolio_history("default")
        self.assertGreaterEqual(len(history), 2)
        # Verify ordering: recorded_at should be ascending
        dates = [h["recorded_at"] for h in history]
        self.assertEqual(dates, sorted(dates))


class TestGetPortfolio(_BaseDbTest):
    """Tests for get_portfolio()."""

    def test_initial_portfolio(self):
        from app.db import get_portfolio

        portfolio = get_portfolio("default")
        self.assertAlmostEqual(portfolio["cash_balance"], 10000.0)
        self.assertEqual(portfolio["positions"], [])
        self.assertAlmostEqual(portfolio["total_value"], 10000.0)

    def test_portfolio_after_buy(self):
        from app.db import execute_trade, get_portfolio

        execute_trade("default", "MSFT", "buy", 5, 300.0)
        portfolio = get_portfolio("default")
        self.assertAlmostEqual(portfolio["cash_balance"], 10000.0 - 1500.0)
        self.assertEqual(len(portfolio["positions"]), 1)
        self.assertEqual(portfolio["positions"][0]["ticker"], "MSFT")


if __name__ == "__main__":
    unittest.main()
