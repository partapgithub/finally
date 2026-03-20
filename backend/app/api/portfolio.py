"""Portfolio API routes.

GET  /portfolio         — current positions enriched with live prices
POST /portfolio/trade   — execute a market order
GET  /portfolio/history — portfolio value snapshots over time
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.db import execute_trade, get_portfolio, get_portfolio_history

router = APIRouter(tags=["portfolio"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str

    @field_validator("side")
    @classmethod
    def side_must_be_valid(cls, v: str) -> str:
        v = v.lower()
        if v not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("quantity must be positive")
        return v

    @field_validator("ticker")
    @classmethod
    def ticker_must_be_non_empty(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("ticker must not be empty")
        return v


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/portfolio")
def get_portfolio_endpoint():
    """Return current positions enriched with live prices from the price cache.

    Response shape::

        {
            "cash_balance": 9500.0,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 5,
                    "avg_cost": 190.0,
                    "current_price": 192.5,
                    "unrealized_pnl": 12.5,
                    "pnl_pct": 1.32
                }
            ],
            "total_value": 12462.5
        }
    """
    # Import here to avoid circular imports — main.py registers these singletons
    # after the routers are included.
    from app.main import get_price_cache

    cache = get_price_cache()
    portfolio = get_portfolio("default")
    cash_balance: float = portfolio["cash_balance"]

    enriched_positions = []
    positions_value = 0.0

    for pos in portfolio["positions"]:
        ticker: str = pos["ticker"]
        quantity: float = pos["quantity"]
        avg_cost: float = pos["avg_cost"]

        # Use live price if available; fall back to avg_cost (pnl = 0)
        if cache is not None:
            price_update = cache.get(ticker)
            current_price = price_update.price if price_update else avg_cost
        else:
            current_price = avg_cost

        unrealized_pnl = round((current_price - avg_cost) * quantity, 4)
        pnl_pct = round((current_price - avg_cost) / avg_cost * 100, 4) if avg_cost else 0.0
        position_value = current_price * quantity
        positions_value += position_value

        enriched_positions.append(
            {
                "ticker": ticker,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "pnl_pct": pnl_pct,
            }
        )

    total_value = round(cash_balance + positions_value, 4)

    return {
        "cash_balance": cash_balance,
        "positions": enriched_positions,
        "total_value": total_value,
    }


@router.post("/portfolio/trade")
def trade_endpoint(request: TradeRequest):
    """Execute a market order at the current live price.

    Returns 400 if the ticker is not in the price cache (no live price available)
    or if validation fails (insufficient cash/shares).
    """
    from app.main import get_price_cache

    cache = get_price_cache()

    if cache is None:
        raise HTTPException(status_code=503, detail="Price cache not available")

    price_update = cache.get(request.ticker)
    if price_update is None:
        raise HTTPException(
            status_code=400,
            detail=f"Ticker '{request.ticker}' is not in the active price cache. "
                   "Add it to the watchlist first.",
        )

    current_price = price_update.price
    result = execute_trade(
        user_id="default",
        ticker=request.ticker,
        side=request.side,
        quantity=request.quantity,
        price=current_price,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return {
        "success": True,
        "trade_id": result["trade_id"],
        "ticker": request.ticker,
        "side": request.side,
        "quantity": request.quantity,
        "price": current_price,
    }


@router.get("/portfolio/history")
def get_portfolio_history_endpoint():
    """Return portfolio value snapshots over time.

    Response is a list of ``{total_value, recorded_at}`` objects ordered
    chronologically (oldest first).
    """
    return get_portfolio_history("default")
