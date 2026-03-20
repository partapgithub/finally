"""FinAlly FastAPI application entry point.

Initialises the database, starts the market data background task, and registers
all API routers.  Also serves the Next.js static export when it exists.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Load .env from the project root (three levels up from backend/app/main.py)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from app.db import (  # noqa: E402 — must come after load_dotenv
    get_portfolio,
    get_watchlist,
    init_db,
    record_portfolio_snapshot,
)
from app.market import PriceCache, create_market_data_source, create_stream_router  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global singletons — set during lifespan, read via the getter functions below
# ---------------------------------------------------------------------------

_price_cache: PriceCache | None = None
_market_source = None  # MarketDataSource


def get_price_cache() -> PriceCache | None:
    """Return the global PriceCache instance (set during app startup)."""
    return _price_cache


def get_market_source():
    """Return the global MarketDataSource instance (set during app startup)."""
    return _market_source


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------


async def _snapshot_task() -> None:
    """Record a portfolio snapshot every 30 seconds.

    Uses live prices from the cache to compute a more accurate total value
    than the post-trade snapshots (which only have cash at snapshot time).
    """
    while True:
        await asyncio.sleep(30)
        try:
            portfolio = get_portfolio("default")
            cash: float = portfolio["cash_balance"]
            positions_value = 0.0

            if _price_cache is not None:
                for pos in portfolio["positions"]:
                    price_update = _price_cache.get(pos["ticker"])
                    current_price = price_update.price if price_update else pos["avg_cost"]
                    positions_value += current_price * pos["quantity"]
            else:
                # Fallback: use avg_cost when cache is unavailable
                for pos in portfolio["positions"]:
                    positions_value += pos["avg_cost"] * pos["quantity"]

            total_value = cash + positions_value
            record_portfolio_snapshot("default", total_value)
        except Exception:
            logger.exception("Error in snapshot background task")


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _price_cache, _market_source

    # 1. Initialise database (creates tables + seeds default data if needed)
    init_db()
    logger.info("Database initialised")

    # 2. Create price cache
    _price_cache = PriceCache()

    # 3. Load watchlist tickers from DB and start the market data source
    tickers = get_watchlist("default")
    _market_source = create_market_data_source(_price_cache)
    await _market_source.start(tickers)
    logger.info("Market data source started with %d tickers", len(tickers))

    # 4. Register the SSE streaming router now that the cache exists.
    #    (The router was created in module scope below; we bind the cache here.)
    # Note: routers are already included in app; the stream router factory
    # captures the cache reference via closure — see create_stream_router.

    # 5. Start the 30-second portfolio snapshot background task
    snapshot_task = asyncio.create_task(_snapshot_task())

    yield  # ---- application is running ----

    # Shutdown
    snapshot_task.cancel()
    try:
        await snapshot_task
    except asyncio.CancelledError:
        pass

    await _market_source.stop()
    logger.info("Market data source stopped")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="FinAlly",
    description="AI-powered trading workstation",
    version="1.0.0",
    lifespan=lifespan,
)

# SSE streaming router — the factory captures the cache via a closure that is
# evaluated lazily when a request arrives, so the cache will be populated by
# lifespan before any client connects.
#
# We use a thin wrapper so the router can be included at module load time but
# still reference the (not-yet-created) cache via get_price_cache().
from fastapi import APIRouter as _APIRouter  # noqa: E402
from fastapi import Request as _Request  # noqa: E402
from fastapi.responses import StreamingResponse as _StreamingResponse  # noqa: E402

_sse_router = _APIRouter(tags=["streaming"])


@_sse_router.get("/stream/prices")
async def stream_prices_proxy(request: _Request) -> _StreamingResponse:
    """Proxy to the real SSE handler once the price cache is available."""
    cache = get_price_cache()
    if cache is None:
        from fastapi.responses import JSONResponse

        return JSONResponse({"detail": "Price cache not yet initialised"}, status_code=503)

    # Delegate to the canonical SSE generator from the market module
    from app.market.stream import _generate_events

    return _StreamingResponse(
        _generate_events(cache, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Import routers
from app.api.portfolio import router as portfolio_router  # noqa: E402
from app.api.watchlist import router as watchlist_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.api.chat import router as chat_router  # noqa: E402

app.include_router(_sse_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(watchlist_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")

# ---------------------------------------------------------------------------
# Serve Next.js static export (optional)
# ---------------------------------------------------------------------------
_static_dir = os.path.join(_THIS_DIR, "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
    logger.info("Serving static files from %s", _static_dir)
