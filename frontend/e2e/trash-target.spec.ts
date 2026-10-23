import { test, expect, type Page, type Locator } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { menuClick, recenter } from './menu';
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
test('locked 65% canvas and reversible drag-to-trash, cancellation, failures and stale revisions', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(fixture.email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Select Demo files', exact: true }),
  ).toBeVisible();
  const demo = (await api(page, '/items?limit=100')).data.find(
    (x: { name: string }) => x.name === 'Demo files',
  );
  const name = 'Trash target ' + Date.now().toString(36);
  const folder = (
    await api(page, '/folders', 'POST', { name, parent_id: demo.id })
  ).data;
  const child = (
    await api(page, '/folders', 'POST', {
      name: 'Discard folder',
      parent_id: folder.id,
    })
  ).data;
  const nested = (
    await api(page, '/folders', 'POST', {
      name: 'Preserved child',
      parent_id: child.id,
    })
  ).data;
  const file = await page.evaluate(async (parent) => {
    const form = new FormData();
    form.append(
      'metadata',
      JSON.stringify({
        name: 'discard.txt',
        parent_id: parent,
        size_bytes: 12,
      }),
    );
    form.append(
      'file',
      new Blob(['preserve me!'], { type: 'text/plain' }),
      'discard.txt',
    );
    const csrf = document.cookie
      .split('; ')
      .find((x) => x.startsWith('pc_csrf_dev='))!
      .split('=')[1];
    const r = await fetch('/api/uploads', {
      method: 'POST',
      headers: { 'X-CSRF-Token': decodeURIComponent(csrf) },
      body: form,
    });
    if (!r.ok) throw Error('fixture upload ' + r.status);
    return r.json();
  }, folder.id);
  await page
    .getByRole('button', { name: 'Select Demo files', exact: true })
    .dblclick();
  // Search avoids any assumptions about accumulated demo fixture positions.
  await page.getByLabel('Search by name').fill(name);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page
    .getByRole('button', { name: 'Select ' + name, exact: true })
    .dblclick();
  await page.getByRole('button', { name: 'Spatial view', exact: true }).click();
  const node = page.getByRole('button', {
    name: 'Select discard.txt',
    exact: true,
  });
  await expect(node).toBeVisible();
  const bin = page.getByRole('button', {
    name: 'Open Recycle Bin',
    exact: true,
  });
  const scale = async () =>
    expect(
      await page.locator('.spatial-world').getAttribute('style'),
    ).toContain('scale(0.65)');
  await scale();
  await expect(
    page.getByRole('button', { name: /Zoom (in|out)|Fit all/ }),
  ).toHaveCount(0);
  await page.mouse.wheel(0, -600);
  await scale();
  await recenter(page);
  await scale();
  await page.setViewportSize({ width: 820, height: 1180 });
  await scale();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await scale();
  async function dragToBin(target: Locator, cancel = false) {
    const a = await target.boundingBox(),
      b = await bin.boundingBox();
    await page.mouse.move(a!.x + a!.width / 2, a!.y + a!.height / 2);
    await page.mouse.down();
    await page.mouse.move(b!.x + b!.width / 2, b!.y + b!.height / 2, {
      steps: 12,
    });
    await expect(bin).toHaveClass(/drop-active/);
    if (cancel) await target.dispatchEvent('pointercancel', { pointerId: 1 });
    await page.mouse.up();
  }
  const before = (await api(page, `/folders/${folder.id}/positions`)).data;
  let trashRequests = 0;
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().endsWith('/trash')) trashRequests++;
  });
  await dragToBin(node, true);
  expect(trashRequests).toBe(0);
  expect((await api(page, `/folders/${folder.id}/positions`)).data).toEqual(
    before,
  );
  await page.route(`**/items/${file.id}/trash`, (r) =>
    r.fulfill({
      status: 503,
      json: { error: { message: 'Synthetic trash unavailable' } },
    }),
  );
  await dragToBin(node);
  await expect(page.getByRole('alert')).toContainText(
    'Synthetic trash unavailable',
  );
  await expect(node).toBeVisible();
  expect((await api(page, `/folders/${folder.id}/positions`)).data).toEqual(
    before,
  );
  await page.unroute(`**/items/${file.id}/trash`);
  await page.getByRole('button', { name: 'Dismiss canvas error' }).click();
  const renamed = (
    await api(page, `/items/${file.id}`, 'PATCH', {
      name: 'changed.txt',
      expected_revision: file.revision,
    })
  ).data;
  const stale = page.waitForResponse((r) =>
    r.url().endsWith(`/items/${file.id}/trash`),
  );
  await dragToBin(node);
  expect((await stale).status()).toBe(409);
  await expect(page.getByRole('alert')).toContainText('changed');
  expect((await api(page, `/items/${file.id}`)).data.trashed_at).toBeNull();
  await menuClick(page, 'Refresh files');
  const fresh = page.getByRole('button', {
    name: 'Select changed.txt',
    exact: true,
  });
  await expect(fresh).toBeVisible();
  const trashed = page.waitForResponse((r) =>
    r.url().endsWith(`/items/${file.id}/trash`),
  );
  await dragToBin(fresh);
  expect((await trashed).status()).toBe(200);
  await expect(fresh).toHaveCount(0);
  const state = (await api(page, '/trash?limit=100')).data.find(
    (item: { id: string }) => item.id === file.id,
  );
  expect(state.trashed_at).not.toBeNull();
  expect(state.checksum_sha256).toBe(renamed.checksum_sha256);
  const folderNode = page.getByRole('button', {
    name: 'Select Discard folder',
    exact: true,
  });
  const ft = page.waitForResponse((r) =>
    r.url().endsWith(`/items/${child.id}/trash`),
  );
  await dragToBin(folderNode);
  expect((await ft).status()).toBe(200);
  await expect(folderNode).toHaveCount(0);
  expect((await api(page, `/items/${nested.id}`)).status).toBe(404);
  await bin.click();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  fs.mkdirSync(path.join(root, 'docs/evidence/stage7'), { recursive: true });
  await page.screenshot({
    path: path.join(root, 'docs/evidence/stage7/trash-desktop.png'),
  });
  await expect(page.getByRole('list', { name: 'Deleted items' })).toBeVisible();
  for (const id of [file.id, child.id]) {
    const row = (await api(page, '/trash?limit=100')).data.find(
      (x: { id: string }) => x.id === id,
    );
    expect(row).toBeTruthy();
    expect(
      (
        await api(page, `/items/${id}/restore`, 'POST', {
          expected_revision: row.revision,
          parent_id: folder.id,
        })
      ).status,
    ).toBe(200);
  }
  expect((await api(page, `/items/${nested.id}`)).status).toBe(200);
  expect((await api(page, `/items/${file.id}`)).data.checksum_sha256).toBe(
    file.checksum_sha256,
  );
  const recovered = await page.request.get(`/api/items/${file.id}/download`);
  expect(recovered.status()).toBe(200);
  expect(await recovered.text()).toBe('preserve me!');
  await page
    .getByRole('button', { name: 'Back to dashboard', exact: true })
    .click();
  await expect(page.locator('.spatial-status')).toHaveCSS(
    'clip',
    'rect(0px, 0px, 0px, 0px)',
  );
  await scale();
  await page.setViewportSize({ width: 390, height: 844 });
  await menuClick(page, '♧ Recycle Bin');
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Back to dashboard', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(root, 'docs/evidence/stage7/trash-mobile.png'),
  });
  await expect(page.getByRole('list', { name: 'Deleted items' })).toBeVisible();
  await page
    .getByRole('button', { name: 'Back to dashboard', exact: true })
    .click();
  await expect(
    page.getByRole('heading', { name: 'All files', exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 1000 });
  await scale();
  fs.mkdirSync(path.join(root, 'docs/evidence/locked-canvas'), {
    recursive: true,
  });
  await page.screenshot({
    path: path.join(root, 'docs/evidence/locked-canvas/desktop.png'),
  });
});
