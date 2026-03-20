"""Watchlist API routes.

GET    /watchlist         — tickers with current prices
POST   /watchlist         — add a ticker
DELETE /watchlist/{ticker} — remove a ticker
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.db import add_to_watchlist, get_watchlist, remove_from_watchlist

router = APIRouter(tags=["watchlist"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AddTickerRequest(BaseModel):
    ticker: str

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


@router.get("/watchlist")
def get_watchlist_endpoint():
    """Return the watchlist enriched with current prices from the price cache.

    Response shape::

        [
            {
                "ticker": "AAPL",
                "price": 192.5,
                "change": 0.5,
                "change_percent": 0.26,
                "direction": "up"
            }
        ]

    Tickers not yet in the price cache will have null values for price fields.
    """
    from app.main import get_price_cache

    cache = get_price_cache()
    tickers = get_watchlist("default")

    result = []
    for ticker in tickers:
        entry: dict = {"ticker": ticker, "price": None, "change": None, "change_percent": None, "direction": None}

        if cache is not None:
            price_update = cache.get(ticker)
            if price_update is not None:
                entry["price"] = price_update.price
                entry["change"] = price_update.change
                entry["change_percent"] = price_update.change_percent
                entry["direction"] = price_update.direction

        result.append(entry)

    return result


@router.post("/watchlist")
async def add_watchlist_endpoint(request: AddTickerRequest):
    """Add a ticker to the watchlist.

    Also starts tracking the ticker in the market data source so prices
    are available immediately.
    """
    from app.main import get_market_source

    ticker = request.ticker  # already uppercased by validator
    result = add_to_watchlist("default", ticker)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add ticker"))

    # Start tracking in market data source
    market_source = get_market_source()
    if market_source is not None:
        await market_source.add_ticker(ticker)

    return {"success": True, "ticker": ticker}


@router.delete("/watchlist/{ticker}")
async def remove_watchlist_endpoint(ticker: str):
    """Remove a ticker from the watchlist.

    Also stops tracking the ticker in the market data source.
    """
    from app.main import get_market_source

    ticker = ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker must not be empty")

    result = remove_from_watchlist("default", ticker)

    # Stop tracking in market data source
    market_source = get_market_source()
    if market_source is not None:
        await market_source.remove_ticker(ticker)

    return {"success": result["success"], "ticker": ticker}
