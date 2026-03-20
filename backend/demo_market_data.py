"""Market Data Demo Script

Run this script from the backend/ directory to verify the market data
components are working correctly. No running server required.

Usage:
    cd backend
    uv run python demo_market_data.py

Optional — also test the live SSE endpoint (requires the server to be running):
    uv run python demo_market_data.py --sse http://localhost:8000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.request


# ─────────────────────────────────────────────
# ANSI helpers
# ─────────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 50}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 50}{RESET}")


# ─────────────────────────────────────────────
# 1. PriceCache tests
# ─────────────────────────────────────────────

def demo_price_cache() -> None:
    section("1 · PriceCache")

    from app.market.cache import PriceCache

    cache = PriceCache()

    # Empty state
    assert len(cache) == 0, "cache should start empty"
    assert cache.get("AAPL") is None
    ok("cache starts empty")

    # First update — direction should be 'flat'
    u1 = cache.update("AAPL", 190.00)
    assert u1.ticker == "AAPL"
    assert u1.price == 190.00
    assert u1.previous_price == 190.00
    assert u1.direction == "flat"
    assert "AAPL" in cache
    ok(f"first update: AAPL={u1.price}  direction={u1.direction}")

    # Price goes up
    u2 = cache.update("AAPL", 191.50)
    assert u2.direction == "up"
    assert u2.change_percent > 0
    ok(f"uptick: AAPL={u2.price}  change={u2.change:+.4f}  ({u2.change_percent:+.4f}%)")

    # Price goes down
    u3 = cache.update("AAPL", 189.00)
    assert u3.direction == "down"
    ok(f"downtick: AAPL={u3.price}  change={u3.change:+.4f}  ({u3.change_percent:+.4f}%)")

    # Multiple tickers
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 420.00)
    assert len(cache) == 3
    all_prices = cache.get_all()
    assert set(all_prices.keys()) == {"AAPL", "GOOGL", "MSFT"}
    ok(f"multi-ticker snapshot: {sorted(all_prices.keys())}")

    # Version bumps on every update
    v_before = cache.version
    cache.update("AAPL", 192.00)
    assert cache.version == v_before + 1
    ok(f"version counter: {v_before} → {cache.version}")

    # Remove
    cache.remove("GOOGL")
    assert "GOOGL" not in cache
    ok("remove('GOOGL') works")

    # to_dict serialisation
    d = cache.get("AAPL").to_dict()
    assert {"ticker", "price", "previous_price", "timestamp", "change", "change_percent", "direction"} == set(d.keys())
    ok(f"to_dict keys: {sorted(d.keys())}")


# ─────────────────────────────────────────────
# 2. GBMSimulator tests
# ─────────────────────────────────────────────

def demo_gbm_simulator() -> None:
    section("2 · GBMSimulator (math & mechanics)")

    from app.market.simulator import GBMSimulator
    from app.market.seed_prices import SEED_PRICES

    DEFAULT_TICKERS = list(SEED_PRICES.keys())
    sim = GBMSimulator(tickers=DEFAULT_TICKERS)

    # Seed prices loaded
    for ticker in DEFAULT_TICKERS:
        p = sim.get_price(ticker)
        assert p is not None and p > 0, f"{ticker} has no price"
    ok(f"seed prices loaded for: {DEFAULT_TICKERS}")

    # Run 20 ticks and verify prices stay positive and move
    prices_before = {t: sim.get_price(t) for t in DEFAULT_TICKERS}
    changed_count = 0
    for _ in range(20):
        result = sim.step()
        assert len(result) == len(DEFAULT_TICKERS)
        for ticker, price in result.items():
            assert price > 0, f"{ticker} price went non-positive: {price}"
    prices_after = {t: sim.get_price(t) for t in DEFAULT_TICKERS}
    changed_count = sum(1 for t in DEFAULT_TICKERS if prices_after[t] != prices_before[t])
    ok(f"20 steps completed — {changed_count}/{len(DEFAULT_TICKERS)} tickers moved")

    # Print a sample price table
    print()
    print(f"  {'Ticker':<8}  {'Seed':>10}  {'After 20 ticks':>14}  {'Change':>10}")
    print(f"  {'─'*8}  {'─'*10}  {'─'*14}  {'─'*10}")
    for ticker in DEFAULT_TICKERS:
        seed = prices_before[ticker]
        after = prices_after[ticker]
        pct = (after - seed) / seed * 100
        color = GREEN if pct >= 0 else RED
        print(f"  {ticker:<8}  {seed:>10.2f}  {after:>14.2f}  {color}{pct:>+9.4f}%{RESET}")

    # Dynamic add/remove
    sim.add_ticker("PYPL")
    assert "PYPL" in sim.get_tickers()
    assert sim.get_price("PYPL") is not None
    result = sim.step()
    assert "PYPL" in result
    ok("add_ticker('PYPL') — price generated, included in next step")

    sim.remove_ticker("PYPL")
    assert "PYPL" not in sim.get_tickers()
    result = sim.step()
    assert "PYPL" not in result
    ok("remove_ticker('PYPL') — excluded from next step")


# ─────────────────────────────────────────────
# 3. SimulatorDataSource (async lifecycle)
# ─────────────────────────────────────────────

async def demo_simulator_source() -> None:
    section("3 · SimulatorDataSource (async lifecycle)")

    from app.market.cache import PriceCache
    from app.market.simulator import SimulatorDataSource
    from app.market.seed_prices import SEED_PRICES

    DEFAULT_TICKERS = list(SEED_PRICES.keys())
    cache = PriceCache()
    source = SimulatorDataSource(price_cache=cache, update_interval=0.1)

    # Start
    await source.start(DEFAULT_TICKERS)

    # Cache should be seeded immediately (before any background ticks)
    for ticker in DEFAULT_TICKERS:
        assert cache.get(ticker) is not None, f"{ticker} not in cache after start"
    ok(f"cache seeded at start for {len(DEFAULT_TICKERS)} tickers")

    # Let the background loop run for ~0.5 s (≈5 ticks at 0.1s interval)
    v_before = cache.version
    await asyncio.sleep(0.5)
    v_after = cache.version
    assert v_after > v_before, "cache version did not advance — background task not running?"
    ok(f"background loop produced {v_after - v_before} cache updates in 0.5s")

    # Snapshot prices
    snapshot = cache.get_all()
    print()
    print(f"  {'Ticker':<8}  {'Price':>10}  {'Prev':>10}  {'Dir':>6}")
    print(f"  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*6}")
    for ticker, u in sorted(snapshot.items()):
        color = GREEN if u.direction == "up" else (RED if u.direction == "down" else YELLOW)
        arrow = "▲" if u.direction == "up" else ("▼" if u.direction == "down" else "●")
        print(f"  {ticker:<8}  {u.price:>10.2f}  {u.previous_price:>10.2f}  {color}{arrow:>6}{RESET}")

    # Dynamic add during live source
    await source.add_ticker("PYPL")
    assert cache.get("PYPL") is not None
    ok("add_ticker('PYPL') while source is live — price seeded in cache immediately")

    await source.remove_ticker("PYPL")
    assert "PYPL" not in cache
    ok("remove_ticker('PYPL') — removed from cache")

    # Stop
    await source.stop()
    v_stopped = cache.version
    await asyncio.sleep(0.3)
    assert cache.version == v_stopped, "cache still updating after stop()"
    ok("source.stop() — background task halted, cache frozen")


# ─────────────────────────────────────────────
# 4. Factory function
# ─────────────────────────────────────────────

def demo_factory() -> None:
    section("4 · Factory (create_market_data_source)")

    import os
    from app.market.cache import PriceCache
    from app.market.factory import create_market_data_source
    from app.market.simulator import SimulatorDataSource

    # Without MASSIVE_API_KEY → SimulatorDataSource
    os.environ.pop("MASSIVE_API_KEY", None)
    cache = PriceCache()
    source = create_market_data_source(cache)
    assert isinstance(source, SimulatorDataSource)
    ok("no MASSIVE_API_KEY → SimulatorDataSource returned")

    # With a fake key → MassiveDataSource (import check only)
    try:
        os.environ["MASSIVE_API_KEY"] = "fake-key-for-demo"
        from app.market.massive_client import MassiveDataSource
        source2 = create_market_data_source(cache)
        assert isinstance(source2, MassiveDataSource)
        ok("MASSIVE_API_KEY set → MassiveDataSource returned")
    except Exception as exc:
        print(f"  {YELLOW}⚠{RESET}  MassiveDataSource check skipped: {exc}")
    finally:
        os.environ.pop("MASSIVE_API_KEY", None)


# ─────────────────────────────────────────────
# 5. Live SSE endpoint (optional)
# ─────────────────────────────────────────────

def demo_sse_endpoint(base_url: str) -> None:
    section(f"5 · Live SSE Endpoint  ({base_url}/api/stream/prices)")

    url = f"{base_url.rstrip('/')}/api/stream/prices"
    print(f"  Connecting to {url} …")

    try:
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                fail(f"HTTP {resp.status} — expected 200")
                return
            ok(f"HTTP {resp.status} OK  (Content-Type: {resp.headers.get('Content-Type', '?')})")

            events_received = 0
            start = time.time()
            raw = b""

            # Read until we have 3 complete SSE events or 4s elapsed
            while events_received < 3 and time.time() - start < 4:
                chunk = resp.read(4096)
                if not chunk:
                    break
                raw += chunk
                events_received = raw.count(b"\n\n")

            lines = raw.decode().splitlines()
            data_lines = [l for l in lines if l.startswith("data:")]

            if not data_lines:
                fail("no data: lines received")
                return

            # Parse the most recent data event
            payload = json.loads(data_lines[-1][len("data:"):].strip())
            tickers = sorted(payload.keys())
            ok(f"received {len(data_lines)} data event(s) covering {len(tickers)} tickers")

            print()
            print(f"  {'Ticker':<8}  {'Price':>10}  {'Direction':>10}  {'Change%':>10}")
            print(f"  {'─'*8}  {'─'*10}  {'─'*10}  {'─'*10}")
            for ticker in tickers:
                info = payload[ticker]
                direction = info.get("direction", "?")
                color = GREEN if direction == "up" else (RED if direction == "down" else YELLOW)
                pct = info.get("change_percent", 0)
                print(f"  {ticker:<8}  {info['price']:>10.2f}  {color}{direction:>10}{RESET}  {pct:>+9.4f}%")

    except TimeoutError:
        fail("connection timed out — is the server running?")
    except OSError as exc:
        fail(f"connection error: {exc}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="FinAlly market data demo")
    parser.add_argument(
        "--sse",
        metavar="URL",
        default=None,
        help="Base URL of a running server (e.g. http://localhost:8000). "
             "If provided, also tests the live SSE endpoint.",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}FinAlly — Market Data Demo{RESET}")
    print("Runs against local Python modules; no running server required.\n")

    errors: list[str] = []

    def run(name: str, fn) -> None:  # noqa: ANN001
        try:
            fn()
        except AssertionError as exc:
            fail(f"ASSERTION FAILED in {name}: {exc}")
            errors.append(name)
        except Exception as exc:
            fail(f"ERROR in {name}: {exc}")
            errors.append(name)

    run("PriceCache", demo_price_cache)
    run("GBMSimulator", demo_gbm_simulator)
    asyncio.run(demo_simulator_source())
    run("Factory", demo_factory)

    if args.sse:
        run("SSE endpoint", lambda: demo_sse_endpoint(args.sse))

    # Summary
    print(f"\n{BOLD}{'─' * 50}{RESET}")
    if errors:
        print(f"{RED}{BOLD}FAILED:{RESET} {', '.join(errors)}")
        sys.exit(1)
    else:
        total = 4 + (1 if args.sse else 0)
        print(f"{GREEN}{BOLD}All {total} demo section(s) passed.{RESET}")


if __name__ == "__main__":
    main()
