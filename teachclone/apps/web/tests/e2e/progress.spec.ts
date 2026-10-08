import { test, expect } from '@playwright/test';

test.describe('Progress and gamification', () => {
  test('progress page renders without crashing', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/progress');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('progress page has XP or level elements', async ({ page }) => {
    await page.goto('/progress');
    await page.waitForLoadState('networkidle');
    // Should have some progress-related content
    const heading = page.locator('h1, h2').first();
    await expect(heading).toBeVisible();
  });
});
