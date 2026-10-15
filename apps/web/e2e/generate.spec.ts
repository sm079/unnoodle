import { expect, test, type Page } from '@playwright/test';
import { mockApi } from './api';

// Queued and running tiles show the prompt as text; a finished one is a link named by it
const newTile = (page: Page) => {
  const gallery = page.getByRole('list', { name: 'Gallery' });
  return gallery.getByText('a poster for a jazz night').or(gallery.getByRole('link', { name: 'a poster for a jazz night' }));
};

test.beforeEach(({ page }) => mockApi(page));

test('/generate fits a phone screen and its composer routes by the inputs', async ({ page }) => {
  await page.goto('/generate');

  const composer = page.getByRole('form', { name: 'Composer' });
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toBeInViewport();
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeInViewport();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, 'page scrolls sideways').toBe(0);

  // Docked at the bottom, leaving most of the screen to the content, with the output type beside Generate
  const viewport = page.viewportSize()!;
  const form = (await composer.boundingBox())!;
  expect(form.y + form.height, 'composer docked at the bottom').toBeGreaterThan(viewport.height - 40);
  expect(form.height, 'composer height').toBeLessThan(viewport.height / 3);
  const toggle = (await composer.getByRole('group', { name: 'Output type' }).boundingBox())!;
  const generate = (await composer.getByRole('button', { name: 'Generate' }).boundingBox())!;
  expect(Math.abs(toggle.y + toggle.height / 2 - (generate.y + generate.height / 2)), 'toggle in the Generate row').toBeLessThan(4);

  // Starts on images. With one model per route, the route chip says what happens and names no model.
  await expect(composer.getByRole('button', { name: 'Route: Create a picture' })).toBeVisible();
  await expect(composer.getByRole('button', { name: 'Shape: Portrait standard' })).toBeVisible();
  await expect(composer.getByRole('button', { name: /^Length/ })).toHaveCount(0);
  await composer.getByRole('button', { name: 'Video', exact: true }).click();
  await expect(composer.getByRole('button', { name: 'Route: Make a video' })).toBeVisible();
  await expect(composer.getByRole('button', { name: 'Length: 5 sec' })).toBeVisible();
  await composer.getByRole('button', { name: 'Image', exact: true }).click();
  await expect(composer.getByRole('button', { name: 'Route: Create a picture' })).toBeVisible();

  // An attached photo is the one to edit, which routes elsewhere and takes its shape from the photo
  await composer.getByRole('button', { name: 'Add from library' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Attach image ast_room' }).click();
  await expect(composer.getByRole('button', { name: 'Role: Edit this' })).toBeVisible();
  await expect(composer.getByRole('button', { name: 'Route: Edit a photo' })).toBeVisible();
  await expect(composer.getByRole('button', { name: /^Shape/ })).toHaveCount(0);

  // As a reference alone it routes nowhere: an edit needs the photo to edit. The route chip says so, and nothing is
  // written under the composer, which is for errors.
  await composer.getByRole('button', { name: 'Role: Edit this' }).click();
  await page.getByRole('menuitemradio', { name: 'Reference' }).click();
  await expect(composer.getByRole('button', { name: 'Route: Not available yet' })).toBeDisabled();
  await expect(composer.getByRole('status')).toHaveCount(0);
  await expect(composer.getByRole('button', { name: 'Generate' })).toHaveAttribute('aria-disabled', 'true');

  await page.getByRole('button', { name: 'Open menu' }).click();
  await expect(page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: 'Home' })).toHaveAttribute('aria-current', 'page');
});

test('Generate sends the inputs with their roles and lets the API pick the workflow', async ({ page }) => {
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('button', { name: 'Video', exact: true }).click();
  await composer.getByRole('button', { name: 'Add from library' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Attach image ast_character' }).click();
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('she turns around');

  const sent = page.waitForRequest(request => request.url().endsWith('/api/generations') && request.method() === 'POST');
  await composer.getByRole('button', { name: 'Generate' }).click();
  expect((await sent).postDataJSON()).toEqual({
    media_type: 'video',
    prompt: 'she turns around',
    inputs: [{ asset_id: 'ast_character', role: 'reference' }],
    params: { quality: 'medium', aspect_ratio: '9:16', duration_s: 5, count: 1, seed: null },
    model: null,
    project_id: null
  });
});

test('after Generate the gallery takes over and follows the generation to its output', async ({ page }) => {
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('a lighthouse at night');
  await composer.getByRole('button', { name: 'Generate' }).click();

  await expect(page.getByRole('heading', { name: 'My generations' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Highlights' })).toHaveCount(0);
  const newest = page.getByRole('list', { name: 'Gallery' }).getByRole('listitem').first();
  await expect(newest.getByRole('progressbar', { name: 'Progress' })).toBeVisible();
  await expect(newest.getByRole('link', { name: 'a lighthouse at night' })).toBeVisible({ timeout: 10_000 });
  // The prompt stays, ready for the next try, with the composer still on screen under the gallery
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toHaveValue('a lighthouse at night');
  await expect(composer.getByRole('button', { name: 'Generate' })).toBeInViewport();
});

test('My generations opens the gallery from the menu', async ({ page }) => {
  await page.goto('/generate');
  await page.getByRole('button', { name: 'Open menu' }).click();
  await page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: 'My generations' }).click();
  await expect(page.getByRole('dialog', { name: 'Menu' })).toHaveCount(0);
  const gallery = page.getByRole('list', { name: 'Gallery' });
  await expect(gallery.getByText('This was too big to make. Try a lower quality, a shorter length or fewer at a time.')).toBeVisible();
});

test('a generation made in a new project is in it and in My generations', async ({ page }) => {
  await page.goto('/generate');
  await page.getByRole('button', { name: 'Open menu' }).click();
  const menu = page.getByRole('dialog', { name: 'Menu' });
  await menu.getByRole('button', { name: 'New project' }).click();
  await menu.getByRole('textbox', { name: 'Project name' }).fill('Posters');
  await menu.getByRole('textbox', { name: 'Project name' }).press('Enter');
  await expect(page.getByRole('heading', { name: 'Posters' })).toBeVisible();

  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('a poster for a jazz night');
  const sent = page.waitForRequest(request => request.url().endsWith('/api/generations') && request.method() === 'POST');
  await composer.getByRole('button', { name: 'Generate' }).click();
  expect((await sent).postDataJSON()).toMatchObject({ project_id: 'prj_new_0' });
  // Stays in the project, where the new generation shows
  await expect(page.getByRole('heading', { name: 'Posters' })).toBeVisible();
  await expect(newTile(page)).toBeVisible();

  // All projects lists My generations first, and My generations has it too
  await page.getByRole('button', { name: 'All projects' }).click();
  await expect(page.getByRole('heading', { name: 'All projects' })).toBeVisible();
  await page
    .getByRole('main')
    .getByRole('button', { name: /^My generations/ })
    .click();
  await expect(page.getByRole('heading', { name: 'My generations' })).toBeVisible();
  await expect(newTile(page)).toBeVisible();
});
