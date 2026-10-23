import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { menuClick } from './menu';
test.use({ actionTimeout: 10000 });
const root = path.resolve(import.meta.dirname, '../..');
const fixture = JSON.parse(
  fs.readFileSync(
    path.join(root, '.cache/stage5-synthetic-fixture.json'),
    'utf8',
  ),
);
const latest = JSON.parse(
  fs.readFileSync(path.join(root, '.cache/compose-latest.json'), 'utf8'),
);
if (
  !latest.passed ||
  fixture.project !== latest.project ||
  latest.project !== 'cloud-stage5-92c8e356b3cb'
)
  throw Error('Requires exact local synthetic preview');
async function api(page: Page, url: string, method = 'GET', body?: unknown) {
  return page.evaluate(
    async ({ url, method, body }) => {
      const token = document.cookie
        .split('; ')
        .find((x) => x.startsWith('pc_csrf_dev='))
        ?.split('=')[1];
      const r = await fetch('/api' + url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'X-CSRF-Token': decodeURIComponent(token) } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      return { status: r.status, data: await r.json() };
    },
    { url, method, body },
  );
}
test('folders default to lists, previews stay intact and root returns to locked canvas', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(fixture.email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const demo = page.getByRole('button', {
    name: 'Select Demo files',
    exact: true,
  });
  await expect(demo).toBeVisible();
  const demoId = (await api(page, '/items?limit=100')).data.find(
    (x: { name: string }) => x.name === 'Demo files',
  ).id;
  const name = 'List navigation ' + Date.now().toString(36);
  const parent = (
    await api(page, '/folders', 'POST', { name, parent_id: demoId })
  ).data;
  await api(page, '/folders', 'POST', {
    name: 'Nested folder',
    parent_id: parent.id,
  });
  await demo.dblclick();
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
  await expect(page.locator('.spatial-world')).toHaveCount(0);
  await page.getByLabel('Search by name').fill(name);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page
    .getByRole('button', { name: 'Select ' + name, exact: true })
    .dblclick();
  await expect(
    page.getByRole('heading', { name, exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.locator('.file-grid')).toHaveCount(0);
  await expect(page.locator('.spatial-world')).toHaveCount(0);
  await page.getByLabel('Choose files to upload').setInputFiles({
    name: 'list-preview.png',
    mimeType: 'image/png',
    buffer: fs.readFileSync(
      path.join(root, '.cache/stage5-browser-fixtures/scene.png'),
    ),
  });
  const file = page.getByRole('button', {
    name: 'Select list-preview.png',
    exact: true,
  });
  await expect(file).toBeVisible();
  await file.dblclick();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Close preview/ })
    .click();
  const close = page.getByRole('button', {
    name: 'Close details',
    exact: true,
  });
  if (await close.isVisible()) await close.click();
  await page
    .getByRole('button', { name: 'Switch to grid view', exact: true })
    .click();
  await expect(page.locator('.file-grid')).toBeVisible();
  await page
    .getByRole('button', { name: 'Select Nested folder', exact: true })
    .click();
  await page
    .getByRole('complementary', { name: 'Item details' })
    .getByRole('button', { name: 'Open', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'Nested folder', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.locator('.file-grid')).toHaveCount(0);
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toHaveCount(1);
  await page
    .getByRole('navigation', { name: 'Folder path' })
    .getByRole('button', { name, exact: false })
    .click();
  await expect(file).toBeVisible();
  await expect(page.locator('.spatial-world')).toHaveCount(0);
  fs.mkdirSync(path.join(root, 'docs/evidence/folder-lists'), {
    recursive: true,
  });
  await page.screenshot({
    path: path.join(root, 'docs/evidence/folder-lists/folder.png'),
  });
  await page
    .getByRole('navigation', { name: 'Folder path' })
    .getByRole('button', { name: 'All files', exact: false })
    .click();
  await expect(page.locator('.spatial-world')).toHaveCount(1);
  expect(await page.locator('.spatial-world').getAttribute('style')).toContain(
    'scale(0.65)',
  );
  await expect(
    page.getByRole('button', { name: 'Open Recycle Bin', exact: true }),
  ).toBeVisible();
  await demo.dblclick();
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
  await menuClick(page, '▱ All files');
  await expect(page.locator('.spatial-world')).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
});
