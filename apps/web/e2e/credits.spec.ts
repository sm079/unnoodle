import { expect, test } from '@playwright/test';
import { mockApi } from './api';

test('without credits Generate is off until an invite code adds some', async ({ page }) => {
  await mockApi(page, { credits: 0 });
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  const generate = composer.getByRole('button', { name: /^Generate/ });

  // A medium picture costs 1
  await expect(generate).toHaveText(/1 credit$/);
  await expect(generate).toHaveAttribute('aria-disabled', 'true');
  await expect(composer.getByText('You have no credits yet. This needs 1.')).toBeVisible();

  const code = composer.getByRole('textbox', { name: 'Invite code' });
  await code.fill('nope');
  await code.press('Enter');
  await expect(composer.getByText("That code doesn't work")).toBeVisible();

  await code.fill('welcome');
  await composer.getByRole('button', { name: 'Add credits' }).click();
  await expect(generate).toHaveAttribute('aria-disabled', 'false');
  await expect(code).toBeHidden();
});
