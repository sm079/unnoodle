import { expect, test } from '@playwright/test';

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
