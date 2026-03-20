# FinAlly Integration Test Report

**Date**: 2026-03-20
**Branch**: agent-teams
**Test runner**: Playwright 1.44
**Backend**: FastAPI / uv (simulator mode, LLM_MOCK=true)

---

## Test Results Summary

| Suite | Tests | Passed | Failed |
|-------|-------|--------|--------|
| API (`specs/api.spec.ts`) | 14 | 14 | 0 |
| UI (`specs/ui.spec.ts`) | 3 | 3 | 0 |
| **Total** | **17** | **17** | **0** |

All tests pass after the fixes described below.

---

## Bugs Found and Fixed

### Bug 1 — Missing `GET /api/chat/history` endpoint (404)

**Severity**: High — causes a client-side crash on every page load
**Symptom**: Browser console showed `Failed to load resource: 404 Not Found @ /api/chat/history`. The `ChatPanel` component calls this endpoint on mount to restore conversation history.
**Root cause**: The frontend `lib/api.ts` defines `fetchChatHistory()` calling `GET /api/chat/history`, but no such route existed in the backend. The DB function `get_chat_history()` and the `chat_messages` table both existed — only the HTTP route was missing.
**Fix**: Added `GET /chat/history` route to `backend/app/api/chat.py` (returns up to 50 messages for the default user). Also updated `get_chat_history()` in `backend/app/db/operations.py` to include the `id` column in its SELECT, since the frontend `ChatMessage` interface requires it.

**Files changed**:
- `backend/app/api/chat.py` — added `GET /chat/history` endpoint
- `backend/app/db/operations.py` — added `id` to `get_chat_history` SELECT query

---

### Bug 2 — `TypeError: Cannot read properties of undefined (reading 'toFixed')` on page load

**Severity**: High — React error boundary triggers, partially breaking the UI
**Symptom**: Immediately after page load, a JS TypeError crashed components that call `.toFixed()` on a `pnl_percent` field that was `undefined`.
**Root cause**: Field name mismatch between backend and frontend. The backend `GET /api/portfolio` returned positions with `pnl_pct` (e.g. `{"pnl_pct": 1.23}`), but the frontend `Position` TypeScript interface declared `pnl_percent: number`. `PortfolioHeatmap` and `PositionsTable` both called `formatPercent(position.pnl_percent)` which called `.toFixed(2)` on `undefined`.
**Fix**: Added `pnl_percent` as an additional field in the portfolio endpoint response (alongside the existing `pnl_pct` to avoid breaking anything else). The position enrichment dict now emits both `pnl_pct` and `pnl_percent` with identical values.

**Files changed**:
- `backend/app/api/portfolio.py` — added `"pnl_percent": pnl_pct` to enriched position dict

---

### Bug 3 — Duplicate watchlist add silently returns 200 (logic bug)

**Severity**: Medium — incorrect API contract; the UNIQUE constraint on `(user_id, ticker)` was intended to prevent duplicates, but the handler swallowed the `IntegrityError` and returned `{"success": true}` instead of an error
**Symptom**: `POST /api/watchlist` with an already-watched ticker (e.g. AAPL) returned HTTP 200 with `{"success": true}` instead of HTTP 400.
**Root cause**: In `backend/app/db/operations.py`, the `add_to_watchlist` function caught `sqlite3.IntegrityError` from the UNIQUE constraint and returned `{"success": True}` — treating a duplicate insert as a non-error.
**Fix**: Changed the `IntegrityError` handler to return `{"success": False, "error": "Ticker '...' is already in the watchlist"}`. The watchlist API route already converts `success=False` to HTTP 400.

**Files changed**:
- `backend/app/db/operations.py` — `add_to_watchlist` now returns error on duplicate

---

### Operational Issue — MASSIVE_API_KEY in .env causes failed polls

**Severity**: Medium — the `.env` file in the project root contains `MASSIVE_API_KEY=fQDEhRUTek6Rl6poZ8a5diyqvs4bMp9U`. This key returns `404 page not found` from the Massive API, meaning all price fetches fail silently. Every ticker ends up with `null` prices, making buy/sell trades impossible (the trade endpoint requires a price in the cache).
**Impact**: Any developer running the backend with this `.env` (without overriding `MASSIVE_API_KEY=`) will get a non-functional app — no prices, no trades.
**Workaround used for tests**: Explicitly set `MASSIVE_API_KEY=""` when starting the backend to force the GBM simulator.
**Recommended fix**: Remove or blank out `MASSIVE_API_KEY` in `.env` / `.env.example`. The simulator is the correct default for development and testing.

---

## Test Coverage

### API Tests (`specs/api.spec.ts`)

| Test | Endpoint | Result |
|------|----------|--------|
| Health check | `GET /api/health` | PASS |
| Watchlist returns 10 tickers | `GET /api/watchlist` | PASS |
| Watchlist has correct default symbols | `GET /api/watchlist` | PASS |
| Add ticker to watchlist | `POST /api/watchlist` | PASS |
| Remove ticker from watchlist | `DELETE /api/watchlist/{ticker}` | PASS |
| Duplicate ticker rejected | `POST /api/watchlist` | PASS (after Bug 3 fix) |
| Initial portfolio has cash | `GET /api/portfolio` | PASS |
| Buy creates position, reduces cash | `POST /api/portfolio/trade` | PASS |
| Sell removes position, restores cash | `POST /api/portfolio/trade` | PASS |
| Sell more than owned → 400 | `POST /api/portfolio/trade` | PASS |
| Buy with insufficient cash → 400 | `POST /api/portfolio/trade` | PASS |
| Portfolio history returns array | `GET /api/portfolio/history` | PASS |
| Chat returns valid response (mock) | `POST /api/chat` | PASS |
| SSE stream has correct content-type | `GET /api/stream/prices` | PASS |

### UI Tests (`specs/ui.spec.ts`)

| Test | Result |
|------|--------|
| Page loads without errors (title present) | PASS |
| Dollar amounts visible in header | PASS |
| Default ticker symbols displayed | PASS |

---

## Backend Startup Checklist

| Item | Status |
|------|--------|
| `uv run uvicorn app.main:app` starts cleanly | OK |
| Database initialized and seeded on first run | OK |
| GBM simulator starts and populates price cache | OK |
| SSE stream serves prices within ~500ms | OK |
| LLM mock mode (`LLM_MOCK=true`) works | OK |
| `GET /api/health` returns 200 | OK |
| Static frontend served from `backend/static/` | OK (requires manual copy of `frontend/out/` → `backend/static/`) |
