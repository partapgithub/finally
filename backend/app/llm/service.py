"""LLM service for FinAlly AI chat assistant.

Handles:
- Portfolio context building
- LiteLLM -> OpenRouter (Cerebras) inference
- Structured JSON response parsing
- Auto-execution of trades and watchlist changes
- Mock mode for testing (LLM_MOCK=true)
"""

from __future__ import annotations

import json
import logging
import os

from dotenv import load_dotenv

from app.db import (
    add_to_watchlist,
    execute_trade,
    get_chat_history,
    get_portfolio,
    get_watchlist,
    remove_from_watchlist,
)

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant for a simulated trading platform.
You help users manage their portfolio, analyze positions, and execute trades.

You MUST respond with valid JSON matching this exact schema:
{
  "message": "Your conversational response to the user",
  "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
  "watchlist_changes": [{"ticker": "PYPL", "action": "add"}]
}

Rules:
- "message" is required, always include it
- "trades" and "watchlist_changes" are optional (omit or use empty arrays)
- Only suggest trades when the user asks or explicitly agrees
- Be concise, data-driven, and professional
- This is simulated money -- be helpful and engaging
- Always respond with ONLY valid JSON, no markdown, no explanation outside the JSON"""

MOCK_RESPONSE = {
    "message": (
        "I'm FinAlly, your AI trading assistant! Your portfolio currently has $10,000 in cash "
        "and is ready to trade. I can help you analyze stocks, suggest trades, or manage your "
        "watchlist. What would you like to do?"
    ),
    "trades": [],
    "watchlist_changes": [],
    "errors": [],
}


def _get_price_cache():
    """Attempt to obtain the shared PriceCache instance from app.main.

    Returns None if app.main is not yet available (e.g., during unit tests).
    """
    try:
        from app.main import get_price_cache  # noqa: PLC0415

        return get_price_cache()
    except (ImportError, AttributeError):
        logger.warning("Could not import get_price_cache from app.main; prices may be unavailable.")
        return None


def _build_portfolio_context(user_id: str, price_cache) -> str:
    """Build a text block describing the user's current portfolio state with live prices."""
    portfolio = get_portfolio(user_id)
    watchlist_tickers = get_watchlist(user_id)

    cash_balance = portfolio["cash_balance"]
    positions = portfolio["positions"]

    # Compute total portfolio value: cash + positions at current prices
    total_positions_value = 0.0
    enriched_positions = []
    for pos in positions:
        ticker = pos["ticker"]
        price_update = price_cache.get(ticker) if price_cache else None
        current_price = price_update.price if price_update else pos["avg_cost"]
        position_value = pos["quantity"] * current_price
        total_positions_value += position_value
        cost_basis = pos["quantity"] * pos["avg_cost"]
        pnl = position_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis != 0 else 0.0
        enriched_positions.append(
            {
                "ticker": ticker,
                "quantity": pos["quantity"],
                "avg_cost": pos["avg_cost"],
                "current_price": current_price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            }
        )

    total_value = cash_balance + total_positions_value

    lines = [
        "Portfolio Context:",
        f"- Cash Balance: ${cash_balance:,.2f}",
        f"- Total Portfolio Value: ${total_value:,.2f} (cash + positions at current prices)",
    ]

    if enriched_positions:
        lines.append("- Positions:")
        for p in enriched_positions:
            pnl_sign = "+" if p["pnl"] >= 0 else ""
            pnl_pct_sign = "+" if p["pnl_pct"] >= 0 else ""
            lines.append(
                f"  - {p['ticker']}: {p['quantity']} shares @ avg ${p['avg_cost']:.2f}, "
                f"current ${p['current_price']:.2f}, "
                f"P&L: {pnl_sign}${p['pnl']:.2f} ({pnl_pct_sign}{p['pnl_pct']:.2f}%)"
            )
    else:
        lines.append("- Positions: None")

    if watchlist_tickers:
        lines.append("- Watchlist (current prices):")
        for ticker in watchlist_tickers:
            price_update = price_cache.get(ticker) if price_cache else None
            if price_update:
                cp_sign = "+" if price_update.change_percent >= 0 else ""
                lines.append(
                    f"  - {ticker}: ${price_update.price:.2f} "
                    f"({cp_sign}{price_update.change_percent:.2f}%)"
                )
            else:
                lines.append(f"  - {ticker}: price unavailable")
    else:
        lines.append("- Watchlist: Empty")

    return "\n".join(lines)


def _call_llm(messages: list[dict]) -> dict:
    """Call LiteLLM -> OpenRouter with the given messages. Returns parsed JSON dict."""
    try:
        import litellm
    except ImportError as exc:
        raise RuntimeError("litellm is not installed. Add it to pyproject.toml.") from exc

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    response = litellm.completion(
        model="openrouter/openai/gpt-oss-120b",
        messages=messages,
        api_base="https://openrouter.ai/api/v1",
        api_key=api_key,
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    content = response.choices[0].message.content
    return json.loads(content)


def process_chat_message(user_message: str, user_id: str = "default") -> dict:
    """Process a user chat message and return the assistant response with executed actions.

    Returns a dict with:
    - message: str -- assistant's conversational response
    - trades_executed: list -- [{ticker, side, quantity, price, success, error}]
    - watchlist_changes_made: list -- [{ticker, action, success}]
    - errors: list -- error strings (empty on full success)
    """
    # Mock mode: return deterministic response without calling LLM
    if os.environ.get("LLM_MOCK", "").lower() == "true":
        return MOCK_RESPONSE.copy()

    # Obtain the shared price cache (may be None in test/dev environments)
    price_cache = _get_price_cache()

    errors: list[str] = []

    # Step 1: Build portfolio context
    try:
        portfolio_context = _build_portfolio_context(user_id, price_cache)
    except Exception as exc:
        logger.exception("Failed to build portfolio context")
        portfolio_context = "Portfolio Context: unavailable"
        errors.append(f"Could not load portfolio context: {exc}")

    # Step 2: Build messages array with last 10 messages of conversation history
    try:
        history = get_chat_history(user_id, limit=10)
    except Exception as exc:
        logger.exception("Failed to load chat history")
        history = []
        errors.append(f"Could not load chat history: {exc}")

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *[{"role": m["role"], "content": m["content"]} for m in history],
        {"role": "user", "content": f"{portfolio_context}\n\nUser: {user_message}"},
    ]

    # Step 3: Call LiteLLM
    try:
        parsed = _call_llm(messages)
    except json.JSONDecodeError as exc:
        logger.exception("LLM returned invalid JSON")
        errors.append(f"LLM returned invalid JSON: {exc}")
        return {
            "message": "I encountered an error processing your request. Please try again.",
            "trades": [],
            "watchlist_changes": [],
            "errors": errors,
        }
    except Exception as exc:
        logger.exception("LLM call failed")
        err_str = str(exc)
        if "Insufficient credits" in err_str or "credits" in err_str.lower():
            user_msg = "AI service unavailable: the OpenRouter account has no credits. Add credits at openrouter.ai or set LLM_MOCK=true to use demo mode."
        elif "APIError" in err_str or "api" in err_str.lower():
            user_msg = "AI service connection error. Check that OPENROUTER_API_KEY is set correctly."
        else:
            user_msg = "I encountered an error connecting to the AI service. Please try again."
        errors.append(f"LLM call failed: {exc}")
        return {
            "message": user_msg,
            "trades": [],
            "watchlist_changes": [],
            "errors": errors,
        }

    # Step 4: Auto-execute trades
    trades_executed: list[dict] = []

    for trade in parsed.get("trades", []):
        ticker = trade.get("ticker", "").upper()
        side = trade.get("side", "")
        quantity = trade.get("quantity", 0)

        if not ticker or not side or not quantity:
            errors.append(f"Skipped malformed trade: {trade}")
            continue

        # Get current price from cache
        current_price: float | None = None
        if price_cache:
            price_update = price_cache.get(ticker)
            if price_update:
                current_price = price_update.price

        if current_price is None:
            error_msg = f"No price available for {ticker}; trade skipped."
            errors.append(error_msg)
            trades_executed.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "quantity": quantity,
                    "price": None,
                    "success": False,
                    "error": error_msg,
                }
            )
            continue

        try:
            result = execute_trade(user_id, ticker, side, quantity, current_price)
        except Exception as exc:
            logger.exception("execute_trade raised an exception for %s", ticker)
            error_msg = f"Trade execution error for {ticker}: {exc}"
            errors.append(error_msg)
            trades_executed.append(
                {
                    "ticker": ticker,
                    "side": side,
                    "quantity": quantity,
                    "price": current_price,
                    "success": False,
                    "error": error_msg,
                }
            )
            continue

        trades_executed.append(
            {
                "ticker": ticker,
                "side": side,
                "quantity": quantity,
                "price": current_price,
                "success": result.get("success", False),
                "error": result.get("error"),
            }
        )
        if not result.get("success"):
            errors.append(f"Trade {side} {quantity} {ticker} failed: {result.get('error')}")

    # Step 4b: Auto-execute watchlist changes
    watchlist_changes_made: list[dict] = []

    for change in parsed.get("watchlist_changes", []):
        ticker = change.get("ticker", "").upper()
        action = change.get("action", "")

        if not ticker or action not in ("add", "remove"):
            errors.append(f"Skipped malformed watchlist change: {change}")
            continue

        try:
            if action == "add":
                result = add_to_watchlist(user_id, ticker)
            else:
                result = remove_from_watchlist(user_id, ticker)
        except Exception as exc:
            logger.exception("Watchlist change raised exception for %s", ticker)
            error_msg = f"Watchlist change error for {ticker}: {exc}"
            errors.append(error_msg)
            watchlist_changes_made.append({"ticker": ticker, "action": action, "success": False})
            continue

        watchlist_changes_made.append(
            {"ticker": ticker, "action": action, "success": result.get("success", False)}
        )

    # Step 5: Return — use "trades" / "watchlist_changes" to match the frontend schema
    return {
        "message": parsed.get("message", "I encountered an error. Please try again."),
        "trades": trades_executed,
        "watchlist_changes": watchlist_changes_made,
        "errors": errors,
    }
