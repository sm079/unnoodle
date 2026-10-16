import { expect, test } from '@playwright/test';
import type { AdminGpu, Gpu } from '../src/lib/types';
import { mockApi } from './api';

const starting: Gpu = {
  state: 'starting',
  phase: 'models:krea2-turbo',
  ready: [],
  eta_s: { 'krea2-turbo': 130, 'flux2-klein-edit': 200, 'minimax-h3': 260 }
};

test('a queued generation says the GPU is starting for it, and about how long', async ({ page }) => {
  await mockApi(page, { gpu: starting });
  await page.goto('/generate');
  await page.getByRole('button', { name: 'Open menu' }).click();
  await page.getByRole('dialog', { name: 'Menu' }).getByRole('button', { name: 'My generations' }).click();
  const gallery = page.getByRole('list', { name: 'Gallery' });
  await expect(gallery.getByText('Starting the GPU · about 2 min')).toBeVisible();
});

test("when today's GPU time is used up, Generate explains instead of charging", async ({ page }) => {
  let posted = false;
  await mockApi(page, { gpu: { state: 'resting', phase: null, ready: [], eta_s: {} } });
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().endsWith('/api/generations')) posted = true;
  });
  await page.goto('/generate');
  const composer = page.getByRole('form', { name: 'Composer' });
  await composer.getByRole('textbox', { name: 'Prompt' }).fill('a lighthouse at night');
  await composer.getByRole('button', { name: 'Generate' }).click();
  const sheet = page.getByRole('dialog', { name: 'Resting until tomorrow' });
  await expect(sheet.getByText('Nothing was charged.')).toBeVisible();
  await sheet.getByRole('button', { name: 'OK' }).click();
  await expect(sheet).toBeHidden();
  // The prompt waits for tomorrow
  await expect(composer.getByRole('textbox', { name: 'Prompt' })).toHaveValue('a lighthouse at night');
  expect(posted).toBe(false);
});

test('admins see the GPU, what it costs, and can stop it', async ({ page }) => {
  await mockApi(page);
  const now = Date.now();
  const live = {
    id: 'gpu_1',
    status: 'preparing' as const,
    phase: 'models:minimax-h3',
    ready: { 'krea2-turbo': new Date(now - 60_000).toISOString(), 'flux2-klein-edit': new Date(now - 20_000).toISOString() },
    requested_by: 'queue',
    gpu_type: 'NVIDIA GeForce RTX 5090',
    cost_per_hour: 1.2,
    stop_reason: null,
    stop_requested: false,
    created_at: new Date(now - 200_000).toISOString(),
    launched_at: new Date(now - 180_000).toISOString(),
    active_at: new Date(now - 30_000).toISOString(),
    stopped_at: null,
    billed_s: 180,
    cost: 0.06
  };
  const earlier = {
    ...live,
    id: 'gpu_0',
    status: 'stopped' as const,
    phase: null,
    stop_reason: 'Idle for 5 minutes',
    created_at: '2026-10-16T06:30:00Z',
    stopped_at: '2026-10-16T06:39:00Z',
    billed_s: 540,
    cost: 0.18
  };
  let stats: AdminGpu = {
    enabled: true,
    gpu: { state: 'starting', phase: 'models:minimax-h3', ready: ['flux2-klein-edit', 'krea2-turbo'], eta_s: { 'minimax-h3': 60 } },
    used_today_s: 720,
    daily_limit_s: 7200,
    idle_stop_s: 300,
    idle_left_s: 270,
    sessions: [live, earlier]
  };
  await page.route('**/api/admin/gpu', route => route.fulfill({ json: stats }));
  await page.route('**/api/admin/gpu/stop', route => {
    stats = {
      ...stats,
      gpu: { state: 'asleep', phase: null, ready: [], eta_s: {} },
      idle_left_s: null,
      sessions: [
        { ...live, status: 'stopped', phase: null, stop_reason: 'Stopped by an admin', stopped_at: new Date().toISOString() },
        earlier
      ]
    };
    return route.fulfill({ json: stats });
  });

  await page.goto('/admin');
  const panel = page.getByRole('tabpanel', { name: 'GPU' });
  await expect(panel.getByText('Getting videos ready')).toBeVisible();
  await expect(panel.getByText('5090 · $1.20/h')).toBeVisible();
  await expect(panel.getByRole('meter', { name: 'GPU time used today' })).toHaveAttribute('aria-valuenow', /^7\d\d/);
  await expect(panel.getByRole('list', { name: 'Ready for' }).getByText('✓ Pictures')).toBeVisible();
  await expect(panel.getByText('Idle for 5 minutes')).toBeVisible();

  await panel.getByRole('button', { name: 'Stop' }).click();
  const sheet = page.getByRole('dialog', { name: 'Stop the GPU?' });
  await sheet.getByRole('button', { name: 'Stop' }).click();
  await expect(sheet).toBeHidden();
  await expect(panel.getByText('Asleep')).toBeVisible();
  await expect(panel.getByText('Stopped by an admin')).toBeVisible();
});
