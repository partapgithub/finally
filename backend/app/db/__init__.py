"""Database layer for the FinAlly trading platform.

Exports all public functions for use by the API layer.
"""

from .schema import get_db_path, init_db
from .operations import (
    add_chat_message,
    add_to_watchlist,
    execute_trade,
    get_chat_history,
    get_portfolio,
    get_portfolio_history,
    get_watchlist,
    record_portfolio_snapshot,
    remove_from_watchlist,
)

__all__ = [
    "init_db",
    "get_db_path",
    "get_portfolio",
    "execute_trade",
    "get_portfolio_history",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "get_chat_history",
    "add_chat_message",
    "record_portfolio_snapshot",
]
