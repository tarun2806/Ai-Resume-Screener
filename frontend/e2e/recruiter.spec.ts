import { test, expect } from '@playwright/test';
import path from 'path';

const REC_EMAIL = 'rec@test.com';
const REC_PASS = 'password123';

test.describe('Recruiter intelligence workflow', () => {
  test('login → screen resume → compare → AI score breakdown', async ({ page }) => {
    await page.goto('/');

    // Auth gate
    await expect(page.getByPlaceholder('Email address')).toBeVisible();
    await page.getByPlaceholder('Email address').fill(REC_EMAIL);
    await page.getByPlaceholder('Password (min 8 chars)').fill(REC_PASS);
    await page.locator('form').getByRole('button', { name: 'Sign In' }).click();

    // Recruiter dashboard
    await expect(page.getByText('Jobs').first()).toBeVisible({ timeout: 15_000 });

    // Select existing job
    await page.getByText('Senior SWE').first().click();
    await expect(page.getByText('Upload Resumes')).toBeVisible();

    // Upload a resume through the real file input
    const docxPath = path.join(import.meta.dirname, 'fixtures', 'strong.docx');
    await page.getByTestId('sync-upload').setInputFiles(docxPath);
    await expect(page.getByText(/Screened \d+ resume/)).toBeVisible({ timeout: 30_000 });

    // Insights strip renders funnel data
    await expect(page.getByText('avg score').first()).toBeVisible();

    // Compare: select two candidates via checkboxes, then run comparison
    const boxes = page.locator('input[type="checkbox"][title="Select for comparison"]');
    const count = await boxes.count();
    test.skip(count < 2, 'Need at least 2 applicants to compare');
    await boxes.nth(0).check();
    await boxes.nth(1).check();
    await page.getByRole('button', { name: /Compare \(2\)/ }).click();

    await expect(page.getByText('Candidate comparison')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Skill coverage matrix')).toBeVisible();

    // Close comparison, expand top candidate -> AI score breakdown
    await page.getByText('Candidate comparison').locator('..').locator('button').last().click();
    const e2eRow = page.locator('div.space-y-2 > div', { hasText: 'E2E Tester' });
    await e2eRow.locator('button').last().click();

    await expect(page.getByText('Score formula (weighted)')).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText('Extraction limitations')).toBeVisible();
    await expect(page.getByText('Resume evidence')).toBeVisible();
  });

  test('unauthenticated users see the auth page', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByPlaceholder('Email address')).toBeVisible();
    await expect(page.locator('form').getByRole('button', { name: 'Sign In' })).toBeVisible();
  });
});
