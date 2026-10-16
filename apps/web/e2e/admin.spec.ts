import { expect, test } from '@playwright/test';
import { generations } from '../src/lib/fixtures';
import type { AdminUser, Invite } from '../src/lib/types';
import { mockApi } from './api';

test('admins delete generations, give credits, make codes and ban words', async ({ page }) => {
  await mockApi(page);
  let listed = generations.map(g => ({ ...g, owner_email: 'person@example.com' }));
  let users: AdminUser[] = [
    { id: 'usr_1', email: 'person@example.com', is_admin: false, balance: 3, generation_count: 4, created_at: '2026-10-16T10:00:00Z' },
    { id: 'usr_e2e', email: 'me@example.com', is_admin: true, balance: 1000, generation_count: 0, created_at: '2026-10-15T10:00:00Z' }
  ];
  let invites: Invite[] = [];
  let words = ['nude', 'gore'];
  await page.route(/\/api\/admin\/generations(\?.*)?$/, route => route.fulfill({ json: listed }));
  await page.route('**/api/admin/generations/*', async route => {
    const id = route.request().url().split('/').at(-1);
    listed = listed.filter(g => g.id !== id);
    return route.fulfill({ status: 204 });
  });
  await page.route('**/api/admin/users', route => route.fulfill({ json: users }));
  await page.route('**/api/admin/users/*/credits', async route => {
    const { amount } = route.request().postDataJSON() as { amount: number };
    users = users.map(u => (u.id === 'usr_1' ? { ...u, balance: u.balance + amount } : u));
    return route.fulfill({ json: users[0] });
  });
  await page.route('**/api/admin/invite-codes', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ json: invites });
    const body = route.request().postDataJSON() as { code: string; credits: number; max_uses: number };
    const made = { ...body, code: body.code.toUpperCase(), uses: 0, expires_at: null, created_at: new Date().toISOString() };
    invites = [made, ...invites];
    return route.fulfill({ status: 201, json: made });
  });
  await page.route(/\/api\/admin\/banned-words(\/.*)?$/, async route => {
    const request = route.request();
    if (request.method() === 'POST') words = [...words, (request.postDataJSON() as { word: string }).word];
    if (request.method() === 'DELETE') words = words.filter(w => w !== decodeURIComponent(request.url().split('/').at(-1)!));
    return route.fulfill({ json: words });
  });

  await page.goto('/admin');
  await page.getByRole('tab', { name: 'Generations' }).click();
  const tiles = page.getByRole('list', { name: "Everyone's generations" }).getByRole('button');
  await expect(tiles.first()).toBeVisible();
  const before = await tiles.count();
  await tiles.first().click();
  const sheet = page.getByRole('dialog', { name: 'Delete this generation?' });
  await sheet.getByRole('button', { name: 'Delete' }).click();
  await expect(sheet).toBeHidden();
  await expect(tiles).toHaveCount(before - 1);

  await page.getByRole('tab', { name: 'People' }).click();
  await page.getByRole('button', { name: 'Give credits to person@example.com' }).click();
  const grant = page.getByRole('dialog', { name: 'Give credits' });
  await grant.getByRole('button', { name: '+100' }).click();
  await grant.getByRole('button', { name: /^Give/ }).click();
  await expect(grant).toBeHidden();
  await expect(page.getByRole('list', { name: 'People' })).toContainText('103 credits');

  await page.getByRole('tab', { name: 'Codes' }).click();
  await page.getByRole('textbox', { name: 'Code' }).fill('spring');
  await page.getByRole('button', { name: 'Make code' }).click();
  await expect(page.getByRole('list', { name: 'Invite codes' })).toContainText('SPRING');

  await page.getByRole('tab', { name: 'Words' }).click();
  await page.getByRole('textbox', { name: 'Word or phrase' }).fill('beheading');
  await page.getByRole('button', { name: 'Ban' }).click();
  const banned = page.getByRole('list', { name: 'Banned words' });
  await expect(banned.getByRole('listitem')).toHaveCount(3);
  await banned.getByRole('button', { name: 'Allow gore' }).click();
  await expect(banned.getByRole('listitem')).toHaveText(['nude', 'beheading']);
});
