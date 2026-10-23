import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { openMenu, closeMenu, menuClick } from './menu';

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
  !latest.project.startsWith('cloud-stage5-')
)
  throw new Error('Requires exact synthetic localhost preview');
const evidence = path.join(root, 'docs/evidence/immersive');
fs.mkdirSync(evidence, { recursive: true });
const ROOT = '00000000-0000-0000-0000-000000000001';
async function login(page: Page) {
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(fixture.email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Open menu', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await expect(page.getByText('Arranging your space…')).toHaveCount(0);
  await openMenu(page);
  const light = page.getByRole('button', { name: '☀ Light mode', exact: true });
  if (await light.isVisible()) await light.click();
  await closeMenu(page);
}
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
async function noPageScroll(page: Page) {
  const bounds = await page.evaluate(() => ({
    width: innerWidth,
    height: innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    scrollHeight: document.documentElement.scrollHeight,
    scrollY,
  }));
  expect(bounds.scrollWidth).toBeLessThanOrEqual(bounds.width);
  expect(bounds.scrollHeight).toBeLessThanOrEqual(bounds.height);
  expect(bounds.scrollY).toBe(0);
}

test('full-screen canvas, closed menu, overlay details, right-edge double click and drawer accessibility', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1600, height: 900 });
  await login(page);
  await expect(
    page.getByRole('dialog', { name: 'Navigation and tools' }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toHaveCount(0);
  const viewport = page.locator('.spatial-viewport');
  expect(await viewport.boundingBox()).toEqual({
    x: 0,
    y: 0,
    width: 1600,
    height: 900,
  });
  await noPageScroll(page);
  await page.screenshot({
    path: path.join(evidence, 'desktop-home.png'),
    fullPage: true,
  });
  const name = 'Immersive ' + Date.now().toString(36);
  const parent = (
    await api(page, '/folders', 'POST', { parent_id: ROOT, name })
  ).data;
  const child = (
    await api(page, '/folders', 'POST', {
      parent_id: parent.id,
      name: 'Edge folder',
    })
  ).data;
  await page.reload();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await openMenu(page);
  await page.getByLabel('Search by name').fill(name);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page
    .getByRole('button', { name: `Select ${name}`, exact: true })
    .dblclick();
  await expect(
    page.getByRole('heading', { name, exact: true, level: 1 }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Spatial view', exact: true }).click();
  await expect(page.locator('.spatial-node')).toHaveCount(1);
  await openMenu(page);
  await page.getByText('Filters & sorting', { exact: true }).click();
  for (let i = 0; i < 2; i++) {
    await page
      .getByRole('button', { name: 'Reset filters', exact: true })
      .click();
    await expect(page.getByText('Opening your space…')).toHaveCount(0);
  }
  await closeMenu(page);
  const positions = (await api(page, `/folders/${parent.id}/positions`)).data;
  const point = await page.locator('.spatial-world').evaluate((el) => {
    const m = new DOMMatrix(getComputedStyle(el).transform);
    return {
      x: (innerWidth - 60 - m.e) / m.a,
      y: (innerHeight / 2 - m.f) / m.a,
    };
  });
  expect(
    (
      await api(page, `/items/${child.id}/position`, 'PATCH', {
        parent_id: parent.id,
        expected_item_revision: child.revision,
        expected_revision: positions[0].revision,
        ...point,
      })
    ).status,
  ).toBe(200);
  const node = page.getByRole('button', {
    name: 'Select Edge folder',
    exact: true,
  });
  await expect
    .poll(() =>
      node.evaluate((el) => parseFloat((el as HTMLElement).style.left)),
    )
    .toBeCloseTo(point.x, 2);
  expect((await node.boundingBox())!.x).toBeGreaterThan(1220);
  await node.dblclick();
  await expect(
    page.getByRole('heading', { name: 'Edge folder', exact: true, level: 1 }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Spatial view', exact: true }).click();
  await openMenu(page);
  const chooser = page.waitForEvent('filechooser');
  await page
    .getByRole('button', { name: '＋ Upload files', exact: true })
    .click();
  await (
    await chooser
  ).setFiles({
    name: 'quiet.png',
    mimeType: 'image/png',
    buffer: fs.readFileSync(
      path.join(root, '.cache/stage5-browser-fixtures/scene.png'),
    ),
  });
  const file = page.getByRole('button', {
    name: 'Select quiet.png',
    exact: true,
  });
  await expect(file).toBeVisible();
  const camera = await page.locator('.spatial-world').getAttribute('style');
  const canvasBounds = await viewport.boundingBox();
  await file.click();
  const details = page.getByRole('complementary', { name: 'Item details' });
  await expect(details).toBeVisible();
  expect(await viewport.boundingBox()).toEqual(canvasBounds);
  expect(await page.locator('.spatial-world').getAttribute('style')).toBe(
    camera,
  );
  expect((await details.boundingBox())!.x).toBeGreaterThanOrEqual(1220);
  await noPageScroll(page);
  await page.screenshot({
    path: path.join(evidence, 'details-overlay.png'),
    fullPage: true,
  });
  await details.getByRole('button', { name: 'Open', exact: true }).click();
  await expect(
    page.getByRole('dialog').getByRole('img', { name: 'quiet.png' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Close preview', exact: true })
    .click();
  await page.keyboard.press('Escape');
  await expect(details).toHaveCount(0);
  await expect(file).toBeFocused();
  await openMenu(page);
  await expect(page.getByLabel('Search by name')).toBeVisible();
  await expect(
    page.getByRole('region', { name: 'Shared storage' }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, 'navigation.png'),
    fullPage: true,
  });
  await page.getByRole('button', { name: 'Close menu', exact: true }).focus();
  await page.keyboard.press('Shift+Tab');
  await expect(
    page.getByRole('button', { name: 'Sign out', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(
    page.getByRole('button', { name: 'Close menu', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('button', { name: 'Open menu', exact: true }),
  ).toBeFocused();
  expect(await page.locator('.spatial-world').getAttribute('style')).toBe(
    camera,
  );
  await openMenu(page);
  await page.getByLabel('Search by name').fill('quiet');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(
    page.getByRole('dialog', { name: 'Navigation and tools' }),
  ).toHaveCount(0);
  await expect(file).toBeVisible();
  await noPageScroll(page);
  await expect(page.locator('.file-main > .success')).toHaveCount(0, {
    timeout: 8000,
  });
  await page.screenshot({
    path: path.join(evidence, 'desktop.png'),
    fullPage: true,
  });
  await file.focus();
  await page.keyboard.press('Enter');
  await expect(details).toBeVisible();
  await expect(
    details.getByRole('button', { name: 'Close details', exact: true }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await menuClick(page, '☾ Dark mode');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.screenshot({
    path: path.join(evidence, 'desktop-dark.png'),
    fullPage: true,
  });
});

test('tablet viewport, mobile list fallback, scrollable menu, folder actions and logout', async ({
  page,
}) => {
  await page.setViewportSize({ width: 820, height: 1180 });
  await login(page);
  for (let i = 0; i < 2; i++) {
    await menuClick(page, '▱ All files');
    await expect(page.getByText('Opening your space…')).toHaveCount(0);
  }
  await noPageScroll(page);
  expect(await page.locator('.spatial-viewport').boundingBox()).toEqual({
    x: 0,
    y: 0,
    width: 820,
    height: 1180,
  });
  await page.screenshot({
    path: path.join(evidence, 'tablet.png'),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
  await noPageScroll(page);
  await openMenu(page);
  await expect(
    page.getByRole('button', { name: 'New folder', exact: true }),
  ).toBeVisible();
  await menuClick(page, 'New folder');
  await expect(page.getByLabel('Folder name')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(
    page.getByRole('button', { name: 'Open menu', exact: true }),
  ).toBeFocused();
  await page.screenshot({
    path: path.join(evidence, 'mobile.png'),
    fullPage: true,
  });
  await openMenu(page);
  await page
    .getByRole('button', { name: 'Sign out', exact: true })
    .scrollIntoViewIfNeeded();
  await noPageScroll(page);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await expect(page.getByLabel('Email address', { exact: true })).toBeVisible();
});
