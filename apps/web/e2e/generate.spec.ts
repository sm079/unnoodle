import { expect, test } from '@playwright/test';
import { generations } from '../src/lib/fixtures';

test('/generate fits a phone screen and its sheets open', async ({ page }) => {
  await page.goto('/generate');

  const gallery = page.getByRole('list', { name: 'Gallery' });
  await expect(gallery.getByRole('listitem')).toHaveCount(generations.length);

  const composer = page.getByRole('form', { name: 'Composer' });
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toBeInViewport();
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeInViewport();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, 'page scrolls sideways').toBe(0);

  await composer.getByRole('button', { name: 'Image' }).click();
  await expect(composer.getByText('Edit image · Flux Klein 9B')).toBeVisible();

  await page.getByRole('button', { name: 'Open library' }).click();
  await expect(page.getByRole('dialog', { name: 'Library' })).toBeVisible();
  await page.keyboard.press('Escape');

  await page.getByRole('button', { name: 'Open settings' }).click();
  await expect(page.getByRole('dialog', { name: 'Settings' })).toBeVisible();
});
