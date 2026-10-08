import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('dashboard page renders without crashing', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    // Page should render something — not be blank
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // No fatal JS errors
    const fatal = errors.filter(e =>
      !e.includes('Warning') &&
      !e.includes('Expected server HTML') &&
      !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('dashboard has expected UI elements', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    // Should have a heading or nav
    const heading = page.locator('h1, h2, nav').first();
    await expect(heading).toBeVisible();
  });
});
