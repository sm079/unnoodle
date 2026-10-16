import { expect, test } from '@playwright/test';

test('the demo opens from the landing page and works without the API', async ({ page }) => {
  // It's served without the API, so it must never call it
  const calls: string[] = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) calls.push(request.url());
  });

  await page.goto('/');
  await page.getByRole('link', { name: 'Look around' }).first().click();
  await expect(page).toHaveURL(/\/demo$/);
  // The hero shows the demo's outputs
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pictures and videos from one prompt');
  await expect(page.locator('main img, main video').first()).toBeVisible();

  // The demo project, from the menu, and one of its results
  await page.getByRole('button', { name: 'Open menu' }).click();
  await page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: 'Demo' }).click();
  const gallery = page.getByRole('list', { name: 'Gallery' });
  await gallery.getByRole('button', { name: 'a paper boat on a puddle, close-up' }).click();
  const result = page.getByRole('dialog', { name: 'Result' });
  await expect(result.getByRole('img', { name: 'a paper boat on a puddle, close-up' })).toBeVisible();
  await expect(result.getByRole('img', { name: 'a paper boat on a puddle, close-up' })).toHaveAttribute('src', /^\/demo\//);

  // Used as input, it attaches like in the app; generating asks the visitor to sign in
  await result.getByRole('button', { name: 'Use as input' }).click();
  const composer = page.getByRole('form', { name: 'Composer' });
  await expect(composer.getByRole('button', { name: 'Mention @photo1 in the prompt' })).toBeVisible();
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('the boat in a storm');
  await composer.getByRole('button', { name: 'Generate' }).click();
  const sheet = page.getByRole('dialog', { name: 'Make your own' });
  await expect(sheet.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/sign-in?next=%2Fgenerate');
  await page.keyboard.press('Escape');

  // So does attaching a file of one's own
  await composer.getByRole('button', { name: 'Attach files' }).click();
  await expect(page.getByRole('dialog', { name: 'Use your own photos' })).toBeVisible();

  expect(calls).toEqual([]);
});
