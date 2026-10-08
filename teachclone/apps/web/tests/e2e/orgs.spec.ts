import { test, expect } from '@playwright/test';

test.describe('Organization pages — full flow', () => {
  test('orgs list page renders with heading', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/orgs');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // Should have a heading mentioning institutes or organizations
    const heading = page.locator('h1').first();
    await expect(heading).toBeVisible();

    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('orgs list has New Institute button', async ({ page }) => {
    await page.goto('/orgs');
    await page.waitForLoadState('networkidle');

    const newBtn = page.locator('button').filter({ hasText: /new institute|create/i }).first();
    await expect(newBtn).toBeVisible();
  });

  test('clicking New Institute reveals create form', async ({ page }) => {
    await page.goto('/orgs');
    await page.waitForLoadState('networkidle');

    const newBtn = page.locator('button').filter({ hasText: /new institute|create/i }).first();
    await newBtn.click();

    // Form fields should appear
    const nameInput = page.locator('input[placeholder*="name" i]').first();
    const slugInput = page.locator('input[placeholder*="slug" i]').first();
    await expect(nameInput).toBeVisible();
    await expect(slugInput).toBeVisible();
  });

  test('create form has name and slug inputs with proper attributes', async ({ page }) => {
    await page.goto('/orgs');
    await page.waitForLoadState('networkidle');

    // Open the create form
    const newBtn = page.locator('button').filter({ hasText: /new institute|create/i }).first();
    await newBtn.click();

    // Name input should accept text
    const nameInput = page.locator('input[placeholder*="name" i]').first();
    await nameInput.fill('Test Institute');
    await expect(nameInput).toHaveValue('Test Institute');

    // Slug input should auto-sanitize
    const slugInput = page.locator('input[placeholder*="slug" i]').first();
    await slugInput.fill('Test Institute!@#');
    const slugValue = await slugInput.inputValue();
    // Slug should only contain lowercase alphanumeric and hyphens
    expect(slugValue).toMatch(/^[a-z0-9-]*$/);
  });

  test('org detail page handles missing id gracefully', async ({ page }) => {
    const response = await page.goto('/orgs/nonexistent-test-id');
    await page.waitForLoadState('networkidle');
    // Should not show a 500 error
    expect(response?.status()).not.toBe(500);

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);
  });

  test('org detail page renders without crashing', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/orgs/test-id');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // No fatal JS errors
    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('org detail page shows Members or Analytics when org exists', async ({ page }) => {
    await page.goto('/orgs/test-id');
    await page.waitForLoadState('networkidle');
    // Wait for potential API response
    await page.waitForTimeout(2000);

    const body = await page.locator('body').innerText();
    // If org loads, it should have Members/Analytics links.
    // If org doesn't exist, it shows spinner/error — both are valid.
    const hasLinks = body.includes('Members') || body.includes('members')
      || body.includes('Analytics') || body.includes('analytics');
    const hasLoading = body.includes('Loading') || body.includes('spinner');
    expect(hasLinks || hasLoading).toBeTruthy();
  });

  test('org members page renders with invite form', async ({ page }) => {
    await page.goto('/orgs/test/members');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // Should have an invite form with email input
    const emailInput = page.locator('input[type="email"], input[placeholder*="email" i]').first();
    await expect(emailInput).toBeVisible();
  });

  test('org members page has role selector', async ({ page }) => {
    await page.goto('/orgs/test/members');
    await page.waitForLoadState('networkidle');

    // Should have a role dropdown (student/teacher/admin)
    const roleSelect = page.locator('select').first();
    await expect(roleSelect).toBeVisible();

    // Should have at least the student option
    const options = await roleSelect.locator('option').allTextContents();
    expect(options.some(o => o.toLowerCase().includes('student'))).toBeTruthy();
  });

  test('org members page has invite button', async ({ page }) => {
    await page.goto('/orgs/test/members');
    await page.waitForLoadState('networkidle');

    const inviteBtn = page.locator('button').filter({ hasText: /invite/i }).first();
    await expect(inviteBtn).toBeVisible();
  });

  test('org analytics page renders leaderboard or empty state', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto('/orgs/test/analytics');
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // Should have analytics heading or top performers section
    const hasAnalytics = body.includes('Analytics') || body.includes('analytics');
    const hasLeaderboard = body.includes('Leaderboard') || body.includes('leaderboard')
      || body.includes('Top Performers') || body.includes('No activity');
    expect(hasAnalytics || hasLeaderboard).toBeTruthy();

    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration')
    );
    expect(fatal).toHaveLength(0);
  });

  test('org analytics has back navigation', async ({ page }) => {
    await page.goto('/orgs/test/analytics');
    await page.waitForLoadState('networkidle');

    // Should have a back link to the org detail page
    const backLink = page.locator('a[href*="/orgs/test"]').first();
    await expect(backLink).toBeVisible();
  });

  test('org members has back navigation', async ({ page }) => {
    await page.goto('/orgs/test/members');
    await page.waitForLoadState('networkidle');

    const backLink = page.locator('a[href*="/orgs/test"]').first();
    await expect(backLink).toBeVisible();
  });

  test('org pages have no console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    const routes = ['/orgs', '/orgs/test-id', '/orgs/test/members', '/orgs/test/analytics'];
    for (const route of routes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');
    }

    const fatal = errors.filter(e =>
      !e.includes('Warning') &&
      !e.includes('Hydration') &&
      !e.includes('Expected server HTML')
    );
    expect(fatal).toHaveLength(0);
  });
});
