import { test, expect } from '@playwright/test';

test.describe('Admin panel', () => {
  test('admin page renders without crashing', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('admin DNA page renders', async ({ page }) => {
    await page.goto('/admin/dna');
    await page.waitForLoadState('networkidle');
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);
  });

  test('admin system page renders', async ({ page }) => {
    await page.goto('/admin/system');
    await page.waitForLoadState('networkidle');
    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);
  });
});
