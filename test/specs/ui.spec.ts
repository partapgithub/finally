import { test, expect } from '@playwright/test';

test.describe('FinAlly Trading Terminal UI', () => {
  test.beforeEach(async ({ page }) => {
    // Give prices time to load
    await page.goto('/');
    await page.waitForTimeout(2000);
  });

  test('loads the page without errors', async ({ page }) => {
    // Page should load and have some content
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });

  test('shows dollar amounts or portfolio value in header', async ({ page }) => {
    // Look for dollar sign somewhere on page (portfolio value or cash)
    const body = await page.locator('body').innerText();
    expect(body).toMatch(/\$[\d,]+/);
  });

  test('displays ticker symbols from default watchlist', async ({ page }) => {
    const body = await page.locator('body').innerText();
    // At least a few of the default tickers should appear
    const tickers = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA'];
    let found = 0;
    for (const ticker of tickers) {
      if (body.includes(ticker)) found++;
    }
    expect(found).toBeGreaterThanOrEqual(3);
  });
});
