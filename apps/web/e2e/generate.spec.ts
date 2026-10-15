import { expect, test } from '@playwright/test';
import { mockApi } from './api';

test.beforeEach(({ page }) => mockApi(page));

test('/generate fits a phone screen and its composer routes by the inputs', async ({ page }) => {
  await page.goto('/generate');

  const composer = page.getByRole('form', { name: 'Composer' });
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toBeInViewport();
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeInViewport();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, 'page scrolls sideways').toBe(0);

  await expect(composer.getByRole('button', { name: 'Route: Text to video · LTX 2.5' })).toBeVisible();
  await expect(composer.getByRole('button', { name: /^Duration/ })).toBeVisible();
  await composer.getByRole('button', { name: 'Image', exact: true }).click();
  await expect(composer.getByRole('button', { name: 'Route: Text to image · Flux Klein 9B' })).toBeVisible();
  await expect(composer.getByRole('button', { name: /^Duration/ })).toHaveCount(0);

  // Another model that does the same
  await composer.getByRole('button', { name: /^Route/ }).click();
  await page.getByRole('dialog').getByRole('button', { name: /Anima/ }).click();
  await expect(composer.getByRole('button', { name: 'Route: Text to image · Anima' })).toBeVisible();

  // An attached image is something to edit, which routes elsewhere
  await composer.getByRole('button', { name: 'Add from library' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Attach image ast_room' }).click();
  await expect(composer.getByRole('button', { name: 'Role: Edit' })).toBeVisible();
  await expect(composer.getByRole('button', { name: 'Route: Edit image · Flux Klein 9B' })).toBeVisible();

  // As a reference it routes nowhere: nothing makes an image from references alone yet
  await composer.getByRole('button', { name: 'Role: Edit' }).click();
  await page.getByRole('menuitemradio', { name: 'Reference' }).click();
  await expect(composer.getByRole('status')).toHaveText('No workflow does image.multi_ref yet');
  await expect(composer.getByRole('button', { name: 'Generate' })).toHaveAttribute('aria-disabled', 'true');

  await page.getByRole('button', { name: 'Open menu' }).click();
  await expect(page.getByRole('dialog', { name: 'Menu' }).getByRole('link', { name: 'Home' })).toBeVisible();
});

test('Generate sends the inputs with their roles and lets the API pick the workflow', async ({ page }) => {
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('button', { name: 'Add from library' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Attach image ast_character' }).click();
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('she turns around');

  const sent = page.waitForRequest(request => request.url().endsWith('/api/generations') && request.method() === 'POST');
  await composer.getByRole('button', { name: 'Generate' }).click();
  expect((await sent).postDataJSON()).toEqual({
    media_type: 'video',
    prompt: 'she turns around',
    inputs: [{ asset_id: 'ast_character', role: 'start_frame', position_s: null }],
    params: { aspect_ratio: '16:9', resolution: '720p', duration_s: 5, count: 1, audio: true, seed: null },
    model: null
  });
});
