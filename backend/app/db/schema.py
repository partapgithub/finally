"""SQLite schema definitions and database initialization for FinAlly."""

import os
import sqlite3
import uuid
from datetime import datetime

# SQL schema definitions
CREATE_USERS_PROFILE = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
);
"""

CREATE_WATCHLIST = """
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);
"""

CREATE_POSITIONS = """
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(user_id, ticker)
);
"""

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
);
"""

CREATE_PORTFOLIO_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
);
"""

CREATE_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
);
"""

ALL_SCHEMAS = [
    CREATE_USERS_PROFILE,
    CREATE_WATCHLIST,
    CREATE_POSITIONS,
    CREATE_TRADES,
    CREATE_PORTFOLIO_SNAPSHOTS,
    CREATE_CHAT_MESSAGES,
]

DEFAULT_WATCHLIST_TICKERS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]


def get_db_path() -> str:
    """Return absolute path to SQLite database file.

    Reads from DB_PATH env var, defaulting to db/finally.db relative to
    the project root. The project root is determined by going up three
    levels from this file (backend/app/db/ -> backend/app/ -> backend/ -> project root).
    """
    db_path = os.environ.get("DB_PATH")
    if db_path:
        return os.path.abspath(db_path)

    # Resolve project root: this file is at backend/app/db/schema.py
    # so project root is three levels up
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(this_dir)))
    return os.path.join(project_root, "db", "finally.db")


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection with row_factory = sqlite3.Row."""
    db_path = get_db_path()
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables (IF NOT EXISTS) and seed if users_profile is empty."""
    conn = get_connection()
    try:
        with conn:
            # Create all tables
            for schema in ALL_SCHEMAS:
                conn.execute(schema)

        # Check if users_profile is empty (seed needed)
        cursor = conn.execute("SELECT COUNT(*) FROM users_profile")
        count = cursor.fetchone()[0]

        if count == 0:
            _seed_data(conn)
    finally:
        conn.close()


def _seed_data(conn: sqlite3.Connection) -> None:
    """Insert default seed data into an empty database."""
    now = datetime.utcnow().isoformat()

    with conn:
        # Seed default user
        conn.execute(
            "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
            ("default", 10000.0, now),
        )

        # Seed default watchlist
        for ticker in DEFAULT_WATCHLIST_TICKERS:
            conn.execute(
                "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), "default", ticker, now),
            )
