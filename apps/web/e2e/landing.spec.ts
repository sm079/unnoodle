import { expect, test } from '@playwright/test';
import { mockApi } from './api';

test('signed out, the landing page shows what the app makes and leads to an account', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pictures and videos from one prompt');
  await expect(page.getByRole('heading', { name: 'Four things, one box' })).toBeVisible();
  // Real outputs, with the prompts that made them
  await expect(
    page.getByRole('img', { name: 'A red vintage bicycle leaning on a pale blue wall, soft morning light, photo' })
  ).toBeAttached();
  await expect(page.locator('video').first()).toHaveAttribute('src', /\/showcase\/.+\.mp4$/);

  await page.getByRole('navigation').getByRole('link', { name: 'Get started' }).click();
  await expect(page).toHaveURL(/\/sign-up$/);
});

test('signed in, the landing page sends you to the studio', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');
  await expect(page).toHaveURL(/\/generate$/);
});
