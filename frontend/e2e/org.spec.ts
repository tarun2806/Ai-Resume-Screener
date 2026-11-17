import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000/api/v1';
const JD = 'We need a Senior Software Engineer. Requirements: Python, FastAPI, SQL, 3+ years experience building backend services and REST APIs.';

test.describe('Organization workflows', () => {
  test('create second org, switch, verify job isolation', async ({ page }) => {
    const email = `e2e-org-${Date.now()}@test.com`;
    const reg = await page.request.post(`${API}/auth/register`, {
      data: { email, password: 'password123', name: 'E2E Org Owner', role: 'recruiter' },
    });
    expect(reg.ok()).toBeTruthy();
    const { token } = await reg.json();
    const auth = { Authorization: `Bearer ${token}` };

    const job = await page.request.post(`${API}/ats/jobs`, {
      headers: auth,
      data: { title: 'OrgA Backend Role', description: JD, location: 'Remote' },
    });
    expect(job.ok()).toBeTruthy();

    await page.goto('/');
    await page.getByPlaceholder('Email address').fill(email);
    await page.getByPlaceholder('Password (min 8 chars)').fill('password123');
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click();
    await expect(page.getByTestId('org-switcher')).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText('OrgA Backend Role')).toBeVisible({ timeout: 15_000 });

    page.once('dialog', (d) => d.accept('E2E Second Org'));
    await page.getByRole('button', { name: /New org/ }).click();
    await expect(page.getByTestId('org-switcher')).toContainText('E2E Second Org', { timeout: 15_000 });

    await expect(page.getByText('No jobs yet')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('OrgA Backend Role')).not.toBeVisible();

    await page.getByTestId('org-switcher').selectOption({ index: 0 });
    await expect(page.getByText('OrgA Backend Role')).toBeVisible({ timeout: 15_000 });
  });
});
