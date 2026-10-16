import { expect, test } from '@playwright/test';
import { mockApi, signIn } from './api';

test.beforeEach(({ page }) => mockApi(page, { signedIn: false }));

test('signing in takes you on to where you were going', async ({ page }) => {
  await page.route('**/api/auth/sign-in', async route => {
    const { password } = route.request().postDataJSON() as { password: string };
    if (password !== 'correct horse') return route.fulfill({ status: 401, json: { detail: 'Wrong email or password' } });
    await signIn(page);
    return route.fulfill({ json: { id: 'usr_e2e', email: 'me@example.com', is_admin: true } });
  });

  await page.goto('/generate');
  await expect(page).toHaveURL('/sign-in?next=%2Fgenerate');

  await page.getByLabel('Email').fill('me@example.com');
  await page.getByLabel('Password').fill('wrong horse');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('form', { name: 'Sign in' }).getByRole('alert')).toHaveText('Wrong email or password');

  await page.getByLabel('Password').fill('correct horse');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/generate');
  await expect(page.getByRole('textbox', { name: 'Prompt' })).toBeVisible();
});
