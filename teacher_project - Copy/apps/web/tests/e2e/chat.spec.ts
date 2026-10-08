import { test, expect } from '@playwright/test';

// The chat page requires a running API to load session data.
// We mock the API responses so the full chat UI renders.
const CHAT_URL = '/chat/test-session-id';
const API_BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000';

// Mock session response so the chat page renders
const MOCK_SESSION = {
  id: 'test-session-id',
  teacher_profile: { name: 'Test Teacher', subject: 'Physics' },
  student_profile: { subject: 'Physics', level: 'intermediate', learn_ahead: false },
  current_effective_level: 'intermediate',
  message_count: 0,
  messages: [],
  concept_mastery: {},
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

// Errors expected when the API server is not running for non-mocked calls
const EXPECTED_ERRORS = [
  'Failed to fetch',
  'NetworkError',
  'fetch failed',
  'NotAllowedError', // microphone permission
];

function isExpectedError(msg: string): boolean {
  return EXPECTED_ERRORS.some(e => msg.includes(e));
}

// Intercept API calls and return mock data
async function mockApi(page: import('@playwright/test').Page) {
  // Mock session endpoint
  await page.route('**/sessions/test-session-id', route => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SESSION),
    });
  });

  // Mock any other API calls that might fail
  await page.route('**/api/**', route => {
    // Let through non-API routes
    if (!route.request().url().includes('localhost:8000')) {
      route.fallback();
      return;
    }
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({}),
    });
  });
}

test.describe('Chat page — image upload and messaging', () => {
  test('chat page renders with session data', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const body = await page.locator('body').innerText();
    expect(body.length).toBeGreaterThan(0);

    // Should show the teacher name from mocked session
    expect(body).toContain('Test Teacher');

    const fatal = errors.filter(e =>
      !e.includes('Warning') && !e.includes('Hydration') && !isExpectedError(e)
    );
    expect(fatal).toHaveLength(0);
  });

  test('chat textarea has maxLength of 10000', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });

    const maxLength = await textarea.getAttribute('maxlength');
    expect(maxLength).toBe('10000');
  });

  test('chat textarea has placeholder text', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });

    const placeholder = await textarea.getAttribute('placeholder');
    expect(placeholder).toBeTruthy();
  });

  test('send button is disabled when textarea is empty', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });

    const sendBtn = page.locator('button[type="submit"]').first();
    const isDisabled = await sendBtn.isDisabled();
    expect(isDisabled).toBeTruthy();
  });

  test('send button enables when text is typed', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });

    await textarea.fill('Hello teacher!');

    const sendBtn = page.locator('button[type="submit"]').first();
    const isDisabled = await sendBtn.isDisabled();
    expect(isDisabled).toBeFalsy();
  });

  test('paperclip button for image attachment is visible', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const attachBtn = page.locator('button[aria-label="Attach image"]');
    await expect(attachBtn).toBeVisible({ timeout: 10000 });
  });

  test('hidden file input accepts only images', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const fileInput = page.locator('input[type="file"]');
    await expect(fileInput).toBeAttached({ timeout: 10000 });

    const accept = await fileInput.getAttribute('accept');
    expect(accept).toBe('image/*');
  });

  test('clicking paperclip opens file dialog', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const attachBtn = page.locator('button[aria-label="Attach image"]');
    await expect(attachBtn).toBeVisible({ timeout: 10000 });

    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      attachBtn.click(),
    ]);

    expect(fileChooser).toBeTruthy();
  });

  test('image preview shows after selecting a file', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const attachBtn = page.locator('button[aria-label="Attach image"]');
    await expect(attachBtn).toBeVisible({ timeout: 10000 });

    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      attachBtn.click(),
    ]);

    // Create a tiny valid PNG file
    const buffer = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      'base64'
    );
    await fileChooser.setFiles({
      name: 'test-image.png',
      mimeType: 'image/png',
      buffer,
    });

    // Preview image should appear
    const preview = page.locator('img[alt="Upload preview"]');
    await expect(preview).toBeVisible({ timeout: 5000 });
  });

  test('image preview has remove button', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const attachBtn = page.locator('button[aria-label="Attach image"]');
    await expect(attachBtn).toBeVisible({ timeout: 10000 });

    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      attachBtn.click(),
    ]);

    const buffer = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      'base64'
    );
    await fileChooser.setFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer,
    });

    const removeBtn = page.locator('button[aria-label="Remove image"]');
    await expect(removeBtn).toBeVisible({ timeout: 5000 });
  });

  test('clicking remove button clears image preview', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const attachBtn = page.locator('button[aria-label="Attach image"]');
    await expect(attachBtn).toBeVisible({ timeout: 10000 });

    const [fileChooser] = await Promise.all([
      page.waitForEvent('filechooser'),
      attachBtn.click(),
    ]);

    const buffer = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      'base64'
    );
    await fileChooser.setFiles({
      name: 'test.png',
      mimeType: 'image/png',
      buffer,
    });

    const preview = page.locator('img[alt="Upload preview"]');
    await expect(preview).toBeVisible({ timeout: 5000 });

    const removeBtn = page.locator('button[aria-label="Remove image"]');
    await removeBtn.click();

    await expect(preview).not.toBeVisible({ timeout: 3000 });
  });

  test('audio toggle checkbox is present', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const audioToggle = page.locator('input[type="checkbox"]').first();
    await expect(audioToggle).toBeVisible({ timeout: 10000 });
  });

  test('checkpoint button is present', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const checkpointBtn = page.locator('button').filter({ hasText: /checkpoint/i }).first();
    await expect(checkpointBtn).toBeVisible({ timeout: 10000 });
  });

  test('chat has at least 3 control buttons (attach, mic, send)', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    // Wait for the form to render
    await page.locator('textarea').first().waitFor({ state: 'visible', timeout: 10000 });

    const buttons = page.locator('form button');
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('send button respects maxLength — enabled at exactly 10000 chars', async ({ page }) => {
    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');

    const textarea = page.locator('textarea').first();
    await expect(textarea).toBeVisible({ timeout: 10000 });

    const longText = 'a'.repeat(10000);
    await textarea.fill(longText);

    const sendBtn = page.locator('button[type="submit"]').first();
    const isDisabled = await sendBtn.isDisabled();
    expect(isDisabled).toBeFalsy();
  });

  test('chat page has no fatal console errors on load', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));

    await mockApi(page);
    await page.goto(CHAT_URL);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const fatal = errors.filter(e =>
      !e.includes('Warning') &&
      !e.includes('Hydration') &&
      !e.includes('Expected server HTML') &&
      !isExpectedError(e)
    );
    expect(fatal).toHaveLength(0);
  });
});
