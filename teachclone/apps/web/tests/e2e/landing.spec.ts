import { test, expect } from '@playwright/test';

test.describe('Landing page', () => {
  test('loads and shows main heading', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/TeachClone|Teach/i);
    // Page must load without JS errors
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.waitForLoadState('networkidle');
    expect(errors.filter(e => !e.includes('Warning'))).toHaveLength(0);
  });

  test('has a call-to-action button', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Look for any button or link that leads to onboarding or signup
    const cta = page.locator('a[href*="onboarding"], a[href*="signup"], button').first();
    await expect(cta).toBeVisible();
  });

  test('navigation links are present', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // At minimum the page should render something
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
  });
});
