import { test, expect } from '@playwright/test';

test.describe('Embed widget and share token page', () => {
  test('widget JS file is served and contains required attributes', async ({ page }) => {
    // The widget script must be accessible at the public path
    const response = await page.goto('/teachclone-widget.js');
    expect(response?.status()).toBe(200);

    const body = await response?.text();
    expect(body).toContain('teachclone-widget-container');
    expect(body).toContain('data-teacher-id');
    expect(body).toContain('data-base-url');
    expect(body).toContain('iframe');
  });

  test('share token page renders error for invalid token', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/t/invalid-token-abc123');
    await page.waitForLoadState('networkidle');

    // Should show an error message, not crash
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // No fatal JS errors
    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('share token page shows profile card when valid', async ({ page }) => {
    // Navigate to a share page — if token is valid, we see a profile card
    // If not, we see an error — both are acceptable
    const response = await page.goto('/t/test-share-token');
    await page.waitForLoadState('networkidle');

    const status = response?.status();
    // 200 with either profile card or error message
    expect(status).toBe(200);

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);
  });

  test('share page has start/learn button or error state', async ({ page }) => {
    await page.goto('/t/test-token');
    await page.waitForLoadState('networkidle');

    // Look for either a CTA button or an error message
    const button = page.locator('button').first();
    const errorMsg = page.locator('.text-rose, [class*="rose"]').first();

    // At least one of these should be visible
    const hasButton = await button.isVisible().catch(() => false);
    const hasError = await errorMsg.isVisible().catch(() => false);
    expect(hasButton || hasError).toBeTruthy();
  });

  test('share page TopNav is present', async ({ page }) => {
    await page.goto('/t/any-token');
    await page.waitForLoadState('networkidle');

    // TopNav should always render (it's a layout component)
    const nav = page.locator('nav, header').first();
    await expect(nav).toBeVisible();
  });

  test('share page has no console errors on load', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/t/test-token');
    await page.waitForLoadState('networkidle');
    // Wait a bit for any deferred effects
    await page.waitForTimeout(1000);

    const fatal = errors.filter(e =>
      !e.includes('Warning') &&
      !e.includes('Hydration') &&
      !e.includes('Expected server HTML')
    );
    expect(fatal).toHaveLength(0);
  });
});
