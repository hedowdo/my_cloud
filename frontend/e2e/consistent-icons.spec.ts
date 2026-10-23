import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { openMenu, closeMenu, recenter } from './menu';
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
  latest.project !== fixture.project ||
  latest.project !== 'cloud-stage5-92c8e356b3cb'
)
  throw Error('Requires exact local synthetic preview');
test('fixed readable nodes across recentering and tablet; manual folders and overlays', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 1600, height: 900 });
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(fixture.email);
  await page.getByLabel('Password', { exact: true }).fill(fixture.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  const node = page.getByRole('button', {
    name: 'Select Demo files',
    exact: true,
  });
  await expect(node).toBeVisible();
  const geometry = async () => {
    const box = await node.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeCloseTo(76, 1);
    expect(box!.height).toBeCloseTo(76, 1);
    expect(
      await page.evaluate(
        () =>
          document.documentElement.scrollHeight <= innerHeight &&
          document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  };
  await geometry();
  await expect(page.getByRole('button', { name: /Zoom (in|out)/ })).toHaveCount(
    0,
  );
  await recenter(page);
  await geometry();
  const camera = await page.locator('.spatial-world').getAttribute('style');
  await node.click();
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toBeVisible();
  expect(await page.locator('.spatial-world').getAttribute('style')).toBe(
    camera,
  );
  await page.getByRole('button', { name: 'Close details' }).click();
  await node.dblclick();
  await expect(
    page.getByRole('heading', { name: 'Demo files', exact: true, level: 1 }),
  ).toBeVisible();
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Spatial view', exact: true }).click();
  await expect(page.locator('.spatial-node')).not.toHaveCount(0);
  for (const box of await page.locator('.spatial-node').evaluateAll((nodes) =>
    nodes.map((n) => {
      const r = n.getBoundingClientRect();
      return { width: r.width, height: r.height };
    }),
  )) {
    expect(box.width).toBeCloseTo(76, 1);
    expect(box.height).toBeCloseTo(76, 1);
  }
  await page.getByRole('button', { name: 'Go to parent folder' }).click();
  await expect(node).toBeVisible();
  await page.setViewportSize({ width: 820, height: 1180 });
  await recenter(page);
  await geometry();
  await openMenu(page);
  await closeMenu(page);
  await page.screenshot({
    path: path.join(root, 'docs/evidence/consistent-icons/tablet.png'),
  });
  await page.setViewportSize({ width: 1600, height: 900 });
  await recenter(page);
  await page.screenshot({
    path: path.join(root, 'docs/evidence/consistent-icons/desktop.png'),
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole('list', { name: 'Files and folders' }),
  ).toBeVisible();
});
