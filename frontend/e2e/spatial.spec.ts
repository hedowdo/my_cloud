import { openMenu, closeMenu, pan, recenter } from './menu';
import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(import.meta.dirname, '../..');
const fixture = JSON.parse(
  fs.readFileSync(
    path.join(root, '.cache/stage5-synthetic-fixture.json'),
    'utf8',
  ),
);
const member = JSON.parse(
  fs.readFileSync(path.join(root, '.cache/stage5-e2e-member.json'), 'utf8'),
);
const latest = JSON.parse(
  fs.readFileSync(path.join(root, '.cache/compose-latest.json'), 'utf8'),
);
if (
  fixture.project !== latest.project ||
  !latest.project.startsWith('cloud-stage5-')
)
  throw new Error('Requires exact local synthetic preview');
const evidence = path.join(root, 'docs/evidence/stage6');
fs.mkdirSync(evidence, { recursive: true });
const ROOT = '00000000-0000-0000-0000-000000000001';
async function login(page: Page, user = fixture) {
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(user.email);
  await page.getByLabel('Password', { exact: true }).fill(user.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'All files', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await openMenu(page);
  const light = page.getByRole('button', { name: '☀ Light mode', exact: true });
  if (await light.isVisible()) await light.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await closeMenu(page);
}
async function api(page: Page, url: string, method = 'GET', body?: unknown) {
  return page.evaluate(
    async ({ url, method, body }) => {
      const csrf = document.cookie
        .split('; ')
        .find((p) => p.startsWith('pc_csrf_dev='))
        ?.split('=')[1];
      const r = await fetch('/api' + url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(csrf ? { 'X-CSRF-Token': decodeURIComponent(csrf) } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      return { status: r.status, data: await r.json() };
    },
    { url, method, body },
  );
}
async function createFolder(page: Page, name: string, parent_id = ROOT) {
  const r = await api(page, '/folders', 'POST', { name, parent_id });
  expect(r.status).toBe(201);
  return r.data;
}
async function enter(page: Page, name: string) {
  await page
    .getByRole('button', { name: `Select ${name}`, exact: true })
    .dblclick();
  await expect(
    page.getByRole('heading', { name, exact: true, level: 1 }),
  ).toBeVisible();
  // Spatial regression explicitly opts in; folders now open as lists.
  await page.getByRole('button', { name: 'Spatial view', exact: true }).click();
  await expect(page.getByText('Arranging your space…')).toHaveCount(0);
}

test('shared persisted placement, stale retry, fixed-scale pan, reduced motion and mobile fallback', async ({
  page,
  browser,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await login(page);
  const name = 'Spatial ' + Date.now().toString(36);
  const folder = await createFolder(page, name);
  const nodes = [];
  for (let i = 0; i < 5; i++)
    nodes.push(await createFolder(page, `Orbit ${i + 1}`, folder.id));
  await page.reload();
  await enter(page, name);
  await expect(page.locator('.spatial-node')).toHaveCount(5);
  const node = page.getByRole('button', {
    name: 'Select Orbit 1',
    exact: true,
  });
  await expect(node.locator('.spatial-name')).toHaveCSS('opacity', '0');
  await node.hover();
  await expect(node.locator('.spatial-name')).toHaveCSS('opacity', '1');
  await node.click();
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toBeVisible();
  const before = (await api(page, `/folders/${folder.id}/positions`)).data.find(
    (p: { item_id: string }) => p.item_id === nodes[0].id,
  );
  await node.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByText('Placement saved for your circle.')).toHaveText(
    'Placement saved for your circle.',
  );
  let rows = (await api(page, `/folders/${folder.id}/positions`)).data;
  expect(
    rows.find((p: { item_id: string }) => p.item_id === nodes[0].id).x,
  ).toBe(before.x + 20);
  await expect(page.getByRole('button', { name: /Zoom (in|out)/ })).toHaveCount(
    0,
  );
  const closeDetails = page.getByRole('button', {
    name: 'Close details',
    exact: true,
  });
  if (await closeDetails.isVisible()) await closeDetails.click();
  const box = await node.boundingBox();
  expect(box).toBeTruthy();
  const current = rows.find(
    (p: { item_id: string }) => p.item_id === nodes[0].id,
  );
  const dragSaved = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/items/${nodes[0].id}/position`) &&
      response.request().method() === 'PATCH',
  );
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box!.x + box!.width / 2 + 45,
    box!.y + box!.height / 2 + 30,
    { steps: 8 },
  );
  await page.mouse.up();
  expect((await dragSaved).status()).toBe(200);
  await expect(page.getByText('Placement saved for your circle.')).toHaveText(
    'Placement saved for your circle.',
  );
  rows = (await api(page, `/folders/${folder.id}/positions`)).data;
  expect(
    rows.find((p: { item_id: string }) => p.item_id === nodes[0].id).x,
  ).toBeGreaterThan(current.x + 20);
  await pan(page, 'right');
  await recenter(page);
  expect(await page.locator('.spatial-world').getAttribute('style')).toContain(
    'scale(0.65)',
  );
  await page.reload();
  await enter(page, name);
  const persisted = (await api(page, `/folders/${folder.id}/positions`)).data;
  expect(persisted).toEqual(rows);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const other = await context.newPage();
  await login(other, member);
  await enter(other, name);
  const otherNode = other.getByRole('button', {
    name: 'Select Orbit 1',
    exact: true,
  });
  await otherNode.focus();
  await other.keyboard.press('ArrowDown');
  await expect(other.getByText('Placement saved for your circle.')).toHaveText(
    'Placement saved for your circle.',
  );
  // Admin retains the earlier revision until its periodic refresh, forcing a real HTTP conflict.
  await node.focus();
  await page.keyboard.press('ArrowLeft');
  await expect(
    page.getByRole('button', { name: 'Retry my placement' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Retry my placement' }).click();
  await expect(page.getByText('Placement saved for your circle.')).toHaveText(
    'Placement saved for your circle.',
  );
  const shared = (await api(page, `/folders/${folder.id}/positions`)).data;
  await expect
    .poll(
      async () =>
        otherNode.evaluate((el) =>
          Number.parseFloat((el as HTMLElement).style.left),
        ),
      { timeout: 12000 },
    )
    .toBeCloseTo(
      shared.find((p: { item_id: string }) => p.item_id === nodes[0].id).x,
      2,
    );
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(node.locator('.spatial-orb')).toHaveCSS(
    'animation-name',
    'none',
  );
  await node.focus();
  await page.keyboard.press('Enter');
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, 'desktop-light.png'),
    fullPage: true,
  });
  const beforeTheme = await page
    .locator('.spatial-world')
    .getAttribute('style');
  await openMenu(page);
  const theme = page.getByRole('button', { name: /Dark mode/ });
  if (await theme.isVisible()) await theme.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(
    page.getByRole('button', { name: '☀ Light mode', exact: true }),
  ).toBeEnabled();
  await closeMenu(page);
  await expect(page.getByText('Arranging your space…')).toHaveCount(0);
  await expect(page.locator('.spatial-node')).toHaveCount(5);
  expect(await page.locator('.spatial-world').getAttribute('style')).toBe(
    beforeTheme,
  );
  await page.screenshot({
    path: path.join(evidence, 'desktop-dark.png'),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole('region', { name: 'Shared spatial dashboard' }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole('button', { name: 'Close details' }).click();
  await closeMenu(page);
  await page.screenshot({
    path: path.join(evidence, 'mobile.png'),
    fullPage: true,
  });
  await context.close();
  expect(errors).toEqual([]);
});

test('fixed-scale canvas performance at 20, 100 and 500 nodes with bounded animation', async ({
  page,
}) => {
  await login(page);
  const results = [];
  for (const count of [20, 100, 500]) {
    const template = (await api(page, '/browse?limit=1')).data[0];
    const items = Array.from({ length: count }, (_, i) => ({
      ...template,
      id: `10000000-0000-0000-0000-${String(i + 1).padStart(12, '0')}`,
      name: `Benchmark ${i + 1}`,
      has_icon: false,
    }));
    const positions = items.map((item, i) => ({
      item_id: item.id,
      x: Math.cos(i * 2.399963) * (240 + 95 * Math.sqrt(i)),
      y: Math.sin(i * 2.399963) * (240 + 95 * Math.sqrt(i)),
      revision: 1,
    }));
    await page.route('**/api/browse?*', (r) => {
      const u = new URL(r.request().url());
      const offset = Number(u.searchParams.get('offset') ?? 0),
        limit = Number(u.searchParams.get('limit') ?? 100);
      return r.fulfill({ json: items.slice(offset, offset + limit) });
    });
    await page.route('**/positions/initialize', (r) => {
      const ids = new Set(r.request().postDataJSON().item_ids);
      expect(ids.size).toBeLessThanOrEqual(250);
      return r.fulfill({ json: positions.filter((p) => ids.has(p.item_id)) });
    });
    await page.route('**/positions', (r) => r.fulfill({ json: positions }));
    await page.reload();
    await expect(page.locator('.spatial-node')).toHaveCount(count);
    await expect(page.getByText('Arranging your space…')).toHaveCount(0);
    await page.locator('.spatial-more > summary').click();
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Performance.enable');
    await cdp.send('Tracing.start', {
      categories: 'devtools.timeline,blink.user_timing',
      transferMode: 'ReturnAsStream',
    });
    const metrics = await page.evaluate(async () => {
      const frames: number[] = [],
        longTasks: number[] = [];
      const observer = new PerformanceObserver((list) =>
        longTasks.push(...list.getEntries().map((e) => e.duration)),
      );
      observer.observe({ type: 'longtask', buffered: false });
      let previous = performance.now();
      for (let i = 0; i < 180; i++) {
        if (i % 15 === 0)
          (
            document.querySelector(
              `[aria-label="Pan ${i % 30 === 0 ? 'right' : 'left'}"]`,
            ) as HTMLButtonElement
          ).click();
        await new Promise<void>((resolve) =>
          requestAnimationFrame((now) => {
            frames.push(now - previous);
            previous = now;
            resolve();
          }),
        );
      }
      observer.disconnect();
      const sorted = frames.slice(5).sort((a, b) => a - b);
      return {
        median_ms: sorted[Math.floor(sorted.length * 0.5)],
        p95_ms: sorted[Math.floor(sorted.length * 0.95)],
        max_ms: Math.max(...sorted),
        longTasks,
        hardwareConcurrency: navigator.hardwareConcurrency,
        userAgent: navigator.userAgent,
        animated: Array.from(document.querySelectorAll('.spatial-orb')).filter(
          (el) => getComputedStyle(el).animationName !== 'none',
        ).length,
      };
    });
    const done = new Promise<string>((resolve) =>
      cdp.once('Tracing.tracingComplete', (e) => resolve(e.stream)),
    );
    await cdp.send('Tracing.end');
    const stream = await done;
    let trace = '';
    while (true) {
      const chunk = await cdp.send('IO.read', { handle: stream });
      trace += chunk.data;
      if (chunk.eof) break;
    }
    await cdp.send('IO.close', { handle: stream });
    fs.mkdirSync(path.join(root, '.local/stage6-browser'), { recursive: true });
    fs.writeFileSync(
      path.join(root, `.local/stage6-browser/trace-${count}.json`),
      trace,
    );
    results.push({ count, ...metrics });
    fs.writeFileSync(
      path.join(root, '.local/stage6-browser/performance-attempt.json'),
      JSON.stringify(results, null, 2),
    );
    expect(metrics.animated).toBeLessThanOrEqual(40);
    expect(metrics.p95_ms).toBeLessThan(40);
    await page.locator('.spatial-more > summary').click();
    await pan(page, 'down');
    await recenter(page);
    if (count === 500)
      await page.screenshot({
        path: path.join(evidence, '500-nodes.png'),
        fullPage: true,
      });
    if (count === 100) {
      await page.setViewportSize({ width: 820, height: 1180 });
      await recenter(page);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.screenshot({
        path: path.join(evidence, 'tablet.png'),
        fullPage: true,
      });
      await page.setViewportSize({ width: 1440, height: 1000 });
    }
    await page.keyboard.press('Tab');
    await page.locator('.spatial-node').last().focus();
    const last = await page.locator('.spatial-node').last().boundingBox(),
      viewport = await page.locator('.spatial-viewport').boundingBox();
    expect(last!.x).toBeGreaterThanOrEqual(viewport!.x);
    expect(last!.x + last!.width).toBeLessThanOrEqual(
      viewport!.x + viewport!.width,
    );
    await page.unrouteAll({ behavior: 'wait' });
    await cdp.detach();
  }
  fs.writeFileSync(
    path.join(root, '.local/stage6-browser/performance.json'),
    JSON.stringify(results, null, 2),
  );
});

test('canvas file drop, background refresh during drag, cancel and empty-space selection', async ({
  page,
}) => {
  await login(page);
  const folderName = `Canvas inputs ${Date.now().toString(36)}`;
  const parent = await createFolder(page, folderName);
  const item = await createFolder(page, 'Pointer node', parent.id);
  await page.reload();
  await enter(page, folderName);
  const node = page.getByRole('button', {
    name: 'Select Pointer node',
    exact: true,
  });
  await expect(node).toBeVisible();
  const row = (await api(page, `/folders/${parent.id}/positions`)).data[0];
  const box = await node.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box!.x + box!.width / 2 + 35,
    box!.y + box!.height / 2 + 25,
    { steps: 4 },
  );
  const dragged = await node.evaluate((el) => ({
    x: (el as HTMLElement).style.left,
    y: (el as HTMLElement).style.top,
  }));
  const updated = await api(page, `/items/${item.id}/position`, 'PATCH', {
    parent_id: parent.id,
    expected_revision: row.revision,
    expected_item_revision: item.revision,
    x: row.x + 100,
    y: row.y + 100,
  });
  expect(updated.status).toBe(200);
  // The real five-second refresh must not replace an in-progress pointer move.
  await page.waitForTimeout(5500);
  expect(
    await node.evaluate((el) => ({
      x: (el as HTMLElement).style.left,
      y: (el as HTMLElement).style.top,
    })),
  ).toEqual(dragged);
  await page.mouse.up();
  await expect(
    page.getByRole('button', { name: 'Keep shared position' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Keep shared position' }).click();
  expect((await api(page, `/browse?parent_id=${parent.id}`)).data).toHaveLength(
    1,
  );
  await node.click();
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toBeVisible();
  await page
    .locator('.spatial-viewport')
    .click({ position: { x: 120, y: 100 } });
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toHaveCount(0);
  const data = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File(['Canvas file bytes'], 'canvas-drop.txt', {
        type: 'text/plain',
      }),
    );
    return transfer;
  });
  await page
    .locator('.spatial-viewport')
    .dispatchEvent('drop', { dataTransfer: data });
  await data.dispose();
  await expect(
    page.getByRole('button', { name: 'Select canvas-drop.txt', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Select canvas-drop.txt', exact: true })
    .dblclick();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: /Close preview/ })
    .click();
  const canvas = page.locator('.spatial-viewport');
  const world = page.locator('.spatial-world');
  const transform = await world.getAttribute('style');
  const bounds = await canvas.boundingBox();
  await page.mouse.move(bounds!.x + 120, bounds!.y + 100);
  await page.mouse.down();
  await page.mouse.move(bounds!.x + 160, bounds!.y + 130, { steps: 4 });
  await canvas.dispatchEvent('pointercancel', { pointerId: 1 });
  await page.mouse.up();
  expect(await world.getAttribute('style')).toBe(transform);
  await openMenu(page);
  await expect(
    page.getByRole('button', { name: 'List view', exact: true }),
  ).toBeVisible();
  await closeMenu(page);
  expect(transform).toContain('translate');
});
