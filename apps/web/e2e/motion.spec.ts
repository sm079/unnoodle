import { expect, test, type Page } from '@playwright/test';
import { mockApi } from './api';

test.beforeEach(({ page }) => mockApi(page));

const highlights = (page: Page) => page.getByRole('region', { name: 'Highlights' });
const frontCard = (page: Page) => highlights(page).getByRole('button', { name: /^Highlight \d+ of \d+$/ });

test('the highlights move with the arrow keys, a tap on a side card and a swipe', async ({ page }) => {
  await page.goto('/generate');
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 1 of/);

  await frontCard(page).focus();
  await page.keyboard.press('ArrowRight');
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 2 of/);
  await expect(frontCard(page)).toBeFocused();

  await highlights(page).getByRole('button', { name: 'Next highlight' }).click();
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 3 of/);

  // Drag the fan to the left, past a side card's width, and let go
  const box = await frontCard(page).boundingBox();
  if (!box) throw new Error('front card has no box');
  const [x, y] = [box.x + box.width / 2, box.y + box.height / 2];
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 160, y + 4, { steps: 12 });
  await page.mouse.up();
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 4 of/);

  // A short drag settles back without moving on, and doesn't count as a tap
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 20, y, { steps: 4 });
  await page.mouse.up();
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 4 of/);
});

test('composer chips animate in and out, and Generate with no prompt goes back to the prompt', async ({ page }) => {
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  const inputs = composer.getByRole('list', { name: 'Inputs' });
  await expect(inputs).toHaveCount(0);
  await composer.getByRole('button', { name: 'Video', exact: true }).click();

  await composer.getByRole('button', { name: 'Add from library' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /^Attach image/ })
    .first()
    .click();
  await expect(inputs.getByRole('listitem')).toHaveCount(1);

  await composer.getByRole('button', { name: 'Remove @photo1' }).click();
  await expect(inputs).toHaveCount(0);

  await composer.getByRole('button', { name: 'More', exact: true }).click();
  await expect(composer.getByRole('group', { name: 'How many' })).toContainText('2');
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeVisible();

  const prompt = composer.getByRole('textbox', { name: 'Prompt' });
  await prompt.fill('');
  await composer.getByRole('button', { name: /^Generate/ }).click();
  await expect(prompt).toBeFocused();
});

test('with reduced motion, things fade instead of moving', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/generate');

  await expect(page.locator('html')).toHaveCSS('--motion-scale', '0');
  await expect(frontCard(page)).toHaveCSS('animation-name', 'fade-in');

  // Still works, without the motion
  await highlights(page).getByRole('button', { name: 'Next highlight' }).click();
  await expect(frontCard(page)).toHaveAccessibleName(/^Highlight 2 of/);
  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('button', { name: 'Video', exact: true }).click();
  await expect(composer.getByRole('button', { name: /^Length/ })).toBeVisible();
});
