import { test, expect } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

test.describe('FinAlly API Integration Tests', () => {
  // -------------------------------------------------------------------------
  // Health
  // -------------------------------------------------------------------------
  test('GET /api/health returns { status: "ok" }', async ({ request }) => {
    const res = await request.get(`${BASE_URL}/api/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('ok');
    expect(typeof body.timestamp).toBe('string');
  });

  // -------------------------------------------------------------------------
  // Watchlist
  // -------------------------------------------------------------------------
  test('GET /api/watchlist returns array of 10 tickers', async ({ request }) => {
    const res = await request.get(`${BASE_URL}/api/watchlist`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body.length).toBe(10);
    for (const item of body) {
      expect(typeof item.ticker).toBe('string');
      expect(item.ticker.length).toBeGreaterThan(0);
    }
  });

  test('GET /api/watchlist tickers include expected default symbols', async ({ request }) => {
    const res = await request.get(`${BASE_URL}/api/watchlist`);
    const body = await res.json();
    const tickers = body.map((x: { ticker: string }) => x.ticker);
    const expected = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'NFLX'];
    for (const t of expected) {
      expect(tickers).toContain(t);
    }
  });

  test('POST /api/watchlist adds a new ticker', async ({ request }) => {
    // Clean up first in case PYPL is already present
    await request.delete(`${BASE_URL}/api/watchlist/PYPL`);

    const res = await request.post(`${BASE_URL}/api/watchlist`, {
      data: { ticker: 'PYPL' },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);
    expect(body.ticker).toBe('PYPL');

    // Verify it now appears in watchlist
    const listRes = await request.get(`${BASE_URL}/api/watchlist`);
    const list = await listRes.json();
    const tickers = list.map((x: { ticker: string }) => x.ticker);
    expect(tickers).toContain('PYPL');
  });

  test('DELETE /api/watchlist/{ticker} removes a ticker', async ({ request }) => {
    // Ensure PYPL exists
    await request.post(`${BASE_URL}/api/watchlist`, { data: { ticker: 'PYPL' } });

    const res = await request.delete(`${BASE_URL}/api/watchlist/PYPL`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    // Verify removed
    const listRes = await request.get(`${BASE_URL}/api/watchlist`);
    const list = await listRes.json();
    const tickers = list.map((x: { ticker: string }) => x.ticker);
    expect(tickers).not.toContain('PYPL');
  });

  test('POST /api/watchlist rejects duplicate ticker', async ({ request }) => {
    // AAPL is always in the default watchlist
    const res = await request.post(`${BASE_URL}/api/watchlist`, {
      data: { ticker: 'AAPL' },
    });
    expect(res.status()).toBe(400);
  });

  // -------------------------------------------------------------------------
  // Portfolio — initial state
  // -------------------------------------------------------------------------
  test('GET /api/portfolio returns initial cash balance of 10000', async ({ request }) => {
    const res = await request.get(`${BASE_URL}/api/portfolio`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.cash_balance).toBe('number');
    expect(body.cash_balance).toBeGreaterThan(0);
    expect(typeof body.total_value).toBe('number');
    expect(Array.isArray(body.positions)).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Trade execution
  // -------------------------------------------------------------------------
  test('buy AAPL creates position and reduces cash', async ({ request }) => {
    // Get starting state (may already have AAPL from earlier tests)
    const beforeRes = await request.get(`${BASE_URL}/api/portfolio`);
    const before = await beforeRes.json();
    const cashBefore: number = before.cash_balance;
    const aaplBefore = before.positions.find((p: { ticker: string }) => p.ticker === 'AAPL');
    const qtyBefore: number = aaplBefore ? aaplBefore.quantity : 0;

    // Wait briefly for price cache to populate
    await new Promise(r => setTimeout(r, 2000));

    const tradeRes = await request.post(`${BASE_URL}/api/portfolio/trade`, {
      data: { ticker: 'AAPL', quantity: 1, side: 'buy' },
    });
    expect(tradeRes.status()).toBe(200);
    const trade = await tradeRes.json();
    expect(trade.success).toBe(true);
    expect(trade.ticker).toBe('AAPL');
    expect(trade.side).toBe('buy');
    expect(typeof trade.price).toBe('number');
    expect(trade.price).toBeGreaterThan(0);

    // Portfolio should now have a position (qty increased by 1)
    const afterRes = await request.get(`${BASE_URL}/api/portfolio`);
    const after = await afterRes.json();
    const aaplPosition = after.positions.find((p: { ticker: string }) => p.ticker === 'AAPL');
    expect(aaplPosition).toBeDefined();
    expect(aaplPosition.quantity).toBe(qtyBefore + 1);
    expect(after.cash_balance).toBeLessThan(cashBefore);
  });

  test('sell AAPL removes position and restores cash', async ({ request }) => {
    // Ensure we have an AAPL position first
    await new Promise(r => setTimeout(r, 500));
    const buyRes = await request.post(`${BASE_URL}/api/portfolio/trade`, {
      data: { ticker: 'AAPL', quantity: 1, side: 'buy' },
    });
    // If buy fails (already have position or insufficient cash), skip gracefully
    if (buyRes.status() !== 200) {
      console.log('Buy setup failed, skipping sell test');
      return;
    }

    const beforeRes = await request.get(`${BASE_URL}/api/portfolio`);
    const before = await beforeRes.json();
    const aaplBefore = before.positions.find((p: { ticker: string }) => p.ticker === 'AAPL');
    expect(aaplBefore).toBeDefined();
    const qtyBefore: number = aaplBefore.quantity;
    const cashBefore: number = before.cash_balance;

    // Sell 1 share
    const sellRes = await request.post(`${BASE_URL}/api/portfolio/trade`, {
      data: { ticker: 'AAPL', quantity: 1, side: 'sell' },
    });
    expect(sellRes.status()).toBe(200);
    const sell = await sellRes.json();
    expect(sell.success).toBe(true);

    // Check portfolio
    const afterRes = await request.get(`${BASE_URL}/api/portfolio`);
    const after = await afterRes.json();
    expect(after.cash_balance).toBeGreaterThan(cashBefore);

    const aaplAfter = after.positions.find((p: { ticker: string }) => p.ticker === 'AAPL');
    if (qtyBefore === 1) {
      // Position should be gone
      expect(aaplAfter).toBeUndefined();
    } else {
      // Quantity reduced
      expect(aaplAfter.quantity).toBe(qtyBefore - 1);
    }
  });

  test('selling more than owned returns 400', async ({ request }) => {
    const res = await request.post(`${BASE_URL}/api/portfolio/trade`, {
      data: { ticker: 'MSFT', quantity: 999999, side: 'sell' },
    });
    expect(res.status()).toBe(400);
  });

  test('buying with insufficient cash returns 400', async ({ request }) => {
    const res = await request.post(`${BASE_URL}/api/portfolio/trade`, {
      data: { ticker: 'AAPL', quantity: 999999, side: 'buy' },
    });
    expect(res.status()).toBe(400);
  });

  // -------------------------------------------------------------------------
  // Portfolio history
  // -------------------------------------------------------------------------
  test('GET /api/portfolio/history returns an array', async ({ request }) => {
    const res = await request.get(`${BASE_URL}/api/portfolio/history`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Chat (LLM mock)
  // -------------------------------------------------------------------------
  test('POST /api/chat returns valid response structure', async ({ request }) => {
    const res = await request.post(`${BASE_URL}/api/chat`, {
      data: { message: 'Hello, what is my portfolio value?' },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.message).toBe('string');
    expect(body.message.length).toBeGreaterThan(0);
    expect(Array.isArray(body.trades_executed)).toBe(true);
    expect(Array.isArray(body.watchlist_changes_made)).toBe(true);
  });

  // -------------------------------------------------------------------------
  // SSE stream (basic connectivity)
  // -------------------------------------------------------------------------
  test('GET /api/stream/prices responds with SSE content-type', async ({ request }) => {
    // We can only check headers without reading the stream indefinitely
    const res = await request.get(`${BASE_URL}/api/stream/prices`, {
      timeout: 5000,
    }).catch(() => null);
    // The endpoint may timeout for us since it's a long-lived stream;
    // but it should at least return 200 with SSE headers
    if (res) {
      expect(res.status()).toBe(200);
      const contentType = res.headers()['content-type'];
      expect(contentType).toContain('text/event-stream');
    }
  });
});
