"""Data access functions for the FinAlly trading platform."""

import json
import sqlite3
import uuid
from datetime import datetime

from .schema import get_connection


def get_portfolio(user_id: str = "default") -> dict:
    """Return the user's portfolio state.

    Returns a dict with:
    - cash_balance: float
    - positions: list of {ticker, quantity, avg_cost}
    - total_value: cash_balance (positions total_value is computed by caller with live prices)
    """
    conn = get_connection()
    try:
        # Get cash balance
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()

        cash_balance = row["cash_balance"] if row else 0.0

        # Get all positions
        position_rows = conn.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker ASC",
            (user_id,),
        ).fetchall()

        positions = [
            {
                "ticker": r["ticker"],
                "quantity": r["quantity"],
                "avg_cost": r["avg_cost"],
            }
            for r in position_rows
        ]

        return {
            "cash_balance": cash_balance,
            "positions": positions,
            "total_value": cash_balance,
        }
    finally:
        conn.close()


def execute_trade(
    user_id: str, ticker: str, side: str, quantity: float, price: float
) -> dict:
    """Execute a trade with validation.

    BUY: validate cash_balance >= quantity * price; update cash; upsert position with
         weighted avg_cost.
    SELL: validate position.quantity >= quantity; update cash (add quantity*price);
          update position; DELETE row if quantity reaches 0.
    Always records in trades table.
    Always records a portfolio_snapshot after trade.

    Returns {success: bool, error: str|None, trade_id: str|None}
    """
    conn = get_connection()
    try:
        with conn:
            now = datetime.utcnow().isoformat()
            trade_id = str(uuid.uuid4())

            if side == "buy":
                total_cost = quantity * price

                # Validate sufficient cash
                row = conn.execute(
                    "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
                ).fetchone()

                if row is None:
                    return {"success": False, "error": "User not found", "trade_id": None}

                if row["cash_balance"] < total_cost:
                    return {
                        "success": False,
                        "error": (
                            f"Insufficient cash: need ${total_cost:.2f}, "
                            f"have ${row['cash_balance']:.2f}"
                        ),
                        "trade_id": None,
                    }

                # Deduct cash
                conn.execute(
                    "UPDATE users_profile SET cash_balance = cash_balance - ? WHERE id = ?",
                    (total_cost, user_id),
                )

                # Upsert position with weighted average cost
                existing = conn.execute(
                    "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                    (user_id, ticker),
                ).fetchone()

                if existing:
                    old_qty = existing["quantity"]
                    old_avg = existing["avg_cost"]
                    new_qty = old_qty + quantity
                    new_avg = ((old_qty * old_avg) + (quantity * price)) / new_qty
                    conn.execute(
                        """UPDATE positions
                           SET quantity = ?, avg_cost = ?, updated_at = ?
                           WHERE user_id = ? AND ticker = ?""",
                        (new_qty, new_avg, now, user_id, ticker),
                    )
                else:
                    conn.execute(
                        """INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (str(uuid.uuid4()), user_id, ticker, quantity, price, now),
                    )

            elif side == "sell":
                # Validate sufficient shares
                existing = conn.execute(
                    "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                    (user_id, ticker),
                ).fetchone()

                if existing is None or existing["quantity"] < quantity:
                    owned = existing["quantity"] if existing else 0.0
                    return {
                        "success": False,
                        "error": (
                            f"Insufficient shares: trying to sell {quantity}, "
                            f"own {owned:.4f}"
                        ),
                        "trade_id": None,
                    }

                # Add cash
                conn.execute(
                    "UPDATE users_profile SET cash_balance = cash_balance + ? WHERE id = ?",
                    (quantity * price, user_id),
                )

                new_qty = existing["quantity"] - quantity
                if new_qty <= 0:
                    # Delete position row when fully sold
                    conn.execute(
                        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                        (user_id, ticker),
                    )
                else:
                    conn.execute(
                        """UPDATE positions
                           SET quantity = ?, updated_at = ?
                           WHERE user_id = ? AND ticker = ?""",
                        (new_qty, now, user_id, ticker),
                    )
            else:
                return {
                    "success": False,
                    "error": f"Invalid side '{side}': must be 'buy' or 'sell'",
                    "trade_id": None,
                }

            # Record trade
            conn.execute(
                """INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (trade_id, user_id, ticker, side, quantity, price, now),
            )

        # Record portfolio snapshot after trade (outside the transaction so we read
        # the committed cash balance)
        _record_snapshot_internal(conn, user_id)

        return {"success": True, "error": None, "trade_id": trade_id}
    finally:
        conn.close()


def _record_snapshot_internal(conn: sqlite3.Connection, user_id: str) -> None:
    """Record a portfolio snapshot using an existing connection."""
    now = datetime.utcnow().isoformat()
    row = conn.execute(
        "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
    ).fetchone()
    cash_balance = row["cash_balance"] if row else 0.0

    # total_value here is just cash; caller can add position values if needed.
    # The API layer computes full total_value with live prices; for the snapshot
    # recorded after a trade we use cash_balance as the base.
    with conn:
        conn.execute(
            """INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
               VALUES (?, ?, ?, ?)""",
            (str(uuid.uuid4()), user_id, cash_balance, now),
        )


def get_portfolio_history(user_id: str = "default") -> list:
    """Return list of {total_value: float, recorded_at: str} ordered by recorded_at ASC."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT total_value, recorded_at
               FROM portfolio_snapshots
               WHERE user_id = ?
               ORDER BY recorded_at ASC""",
            (user_id,),
        ).fetchall()
        return [{"total_value": r["total_value"], "recorded_at": r["recorded_at"]} for r in rows]
    finally:
        conn.close()


def get_watchlist(user_id: str = "default") -> list:
    """Return list of ticker strings for the user's watchlist."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
            (user_id,),
        ).fetchall()
        return [r["ticker"] for r in rows]
    finally:
        conn.close()


def add_to_watchlist(user_id: str, ticker: str) -> dict:
    """Add ticker to watchlist.

    Returns {success: bool, error: str|None}.
    Returns an error if ticker is already in watchlist (UNIQUE constraint).
    """
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                    (str(uuid.uuid4()), user_id, ticker.upper(), now),
                )
            return {"success": True, "error": None}
        except sqlite3.IntegrityError:
            # UNIQUE constraint — ticker already in watchlist
            return {"success": False, "error": f"Ticker '{ticker.upper()}' is already in the watchlist"}
    finally:
        conn.close()


def remove_from_watchlist(user_id: str, ticker: str) -> dict:
    """Remove ticker from watchlist.

    Returns {success: bool}.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
                (user_id, ticker.upper()),
            )
        return {"success": True}
    finally:
        conn.close()


def get_chat_history(user_id: str = "default", limit: int = 10) -> list:
    """Return last `limit` messages ordered by created_at ASC.

    Each entry: {id, role, content, actions, created_at}
    actions is parsed from JSON string to dict (or None).
    """
    conn = get_connection()
    try:
        # Fetch last `limit` rows (most recent first), then reverse for chronological order
        rows = conn.execute(
            """SELECT id, role, content, actions, created_at
               FROM chat_messages
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()

        messages = []
        for r in reversed(rows):
            actions = None
            if r["actions"] is not None:
                try:
                    actions = json.loads(r["actions"])
                except (json.JSONDecodeError, TypeError):
                    actions = None
            messages.append(
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "actions": actions,
                    "created_at": r["created_at"],
                }
            )
        return messages
    finally:
        conn.close()


def add_chat_message(
    user_id: str, role: str, content: str, actions: dict | None = None
) -> None:
    """Insert a message into chat_messages.

    Serializes actions to a JSON string if not None.
    """
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        actions_json = json.dumps(actions) if actions is not None else None
        with conn:
            conn.execute(
                """INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, role, content, actions_json, now),
            )
    finally:
        conn.close()


def record_portfolio_snapshot(user_id: str, total_value: float) -> None:
    """Insert a portfolio_snapshots row."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        with conn:
            conn.execute(
                """INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at)
                   VALUES (?, ?, ?, ?)""",
                (str(uuid.uuid4()), user_id, total_value, now),
            )
    finally:
        conn.close()
