import { expect, test } from '@playwright/test';

test('/generate fits a phone screen and its composer follows the workflow', async ({ page }) => {
  await page.goto('/generate');

  const composer = page.getByRole('form', { name: 'Composer' });
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toBeInViewport();
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeInViewport();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, 'page scrolls sideways').toBe(0);

  await expect(composer.getByRole('button', { name: /^Duration/ })).toBeVisible();
  await composer.getByRole('button', { name: 'Image', exact: true }).click();
  await expect(composer.getByRole('button', { name: 'Workflow: Flux Klein 9B' })).toBeVisible();
  await expect(composer.getByRole('button', { name: /^Duration/ })).toHaveCount(0);
  await expect(composer.getByRole('button', { name: 'Attach files' })).toBeEnabled();

  await composer.getByRole('button', { name: /^Workflow/ }).click();
  const menu = page.getByRole('dialog');
  await menu.getByRole('textbox', { name: 'Search workflows' }).fill('anima');
  await menu.getByRole('button', { name: /Anima/ }).click();
  await expect(composer.getByRole('button', { name: 'Workflow: Anima' })).toBeVisible();
  // Text to image takes no inputs
  await expect(composer.getByRole('button', { name: 'Attach files' })).toBeDisabled();

  await page.getByRole('button', { name: 'Open menu' }).click();
  await expect(page.getByRole('dialog', { name: 'Menu' }).getByRole('link', { name: 'Home' })).toBeVisible();
});
