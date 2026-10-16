import { expect, test } from '@playwright/test';
import { mockApi } from './api';

test('short of credits, Generate opens a sheet that takes a code and carries on', async ({ page }) => {
  await mockApi(page, { credits: 0 });
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  const generate = composer.getByRole('button', { name: /^Generate/ });

  // A medium picture costs 1, shown on the button, which stays pressable
  await expect(generate).toHaveAccessibleName('Generate 1 credit');
  await expect(generate).toHaveAttribute('aria-disabled', 'false');
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('a poster for a jazz night');
  await generate.click();

  const sheet = page.getByRole('dialog', { name: 'Get more credits' });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole('list', { name: 'Credit packs' }).getByRole('listitem')).toHaveCount(3);

  await sheet.getByRole('button', { name: 'Enter code' }).click();
  const code = sheet.getByRole('textbox', { name: 'Invite code' });
  await code.fill('nope');
  await code.press('Enter');
  await expect(sheet.getByRole('alert')).toHaveText("That code doesn't work");

  const sent = page.waitForRequest(request => request.url().endsWith('/api/generations') && request.method() === 'POST');
  await code.fill('welcome');
  await sheet.getByRole('button', { name: 'Add' }).click();
  await expect(page.getByRole('dialog', { name: "You're all set" })).toBeVisible();
  // Carries on with the request that opened it
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^Generate/ })
    .click();
  await sent;
  await expect(page.getByRole('dialog')).toBeHidden();
});
