import { openMenu, closeMenu, menuClick as navigateMenu } from './menu';
import { test, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

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
  fixture.project !== latest.project ||
  !fixture.project.startsWith('cloud-stage5-')
)
  throw new Error('Requires exact passing local Stage 5 fixture');
const evidence = path.join(root, 'docs/evidence/stage5');
fs.mkdirSync(evidence, { recursive: true });
const assets = path.join(root, '.cache/stage5-browser-fixtures');
const tag = Date.now().toString(36);

async function menuClick(page: Page, name: string) {
  await navigateMenu(page, name);
  if (name === '▱ All files' && (page.viewportSize()?.width ?? 0) >= 768) {
    await expect(page.getByText('Opening your space…')).toHaveCount(0);
    await openMenu(page);
    const list = page.getByRole('button', { name: 'List view', exact: true });
    if (await list.isVisible()) await list.click();
    await closeMenu(page);
  }
}

async function login(
  page: Page,
  email = fixture.email,
  password = fixture.password,
) {
  await page.goto('/');
  await page.getByLabel('Email address', { exact: true }).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'All files', exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await openMenu(page);
  const list = page.getByRole('button', { name: 'List view', exact: true });
  if (await list.isVisible()) await list.click();
  const light = page.getByRole('button', { name: '☀ Light mode', exact: true });
  if (await light.isVisible()) await light.click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await closeMenu(page);
}

async function uploaded(page: Page, name: string, body: string) {
  await closeMenu(page);
  await page.getByLabel('Choose files to upload').setInputFiles({
    name,
    mimeType: 'application/octet-stream',
    buffer: Buffer.from(body),
  });
}
async function select(page: Page, name: string) {
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  if (
    (await page
      .getByRole('button', { name: `Select ${name}`, exact: true })
      .count()) === 0 &&
    (await page.getByLabel('Search by name').isVisible())
  )
    await search(page, name);
  await page
    .getByRole('button', { name: `Select ${name}`, exact: true })
    .click();
  await expect(
    page.getByRole('complementary', { name: 'Item details' }),
  ).toBeVisible();
}
async function action(page: Page, name: string) {
  await page
    .getByRole('complementary', { name: 'Item details' })
    .getByRole('button', { name, exact: true })
    .click();
}
async function search(page: Page, text: string) {
  const close = page.getByRole('button', {
    name: 'Close details',
    exact: true,
  });
  if (await close.isVisible()) await close.click();
  await page.getByLabel('Search by name').fill(text);
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
}

async function newest(page: Page) {
  const filters = page.locator('details.filter-panel');
  const opened = await filters.getAttribute('open');
  if (opened === null)
    await page.getByText('Filters & sorting', { exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Sort by', exact: true })
    .selectOption('date');
  await page
    .getByRole('combobox', { name: 'Order', exact: true })
    .selectOption('desc');
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  if (opened === null)
    await page.getByText('Filters & sorting', { exact: true }).click();
}

async function chooseDestination(page: Page, name: string) {
  const dialog = page.getByRole('dialog'),
    target = dialog.getByRole('button', { name: `▱ ${name}`, exact: true });
  await expect(dialog.locator('.folder-choices button').first()).toBeVisible();
  for (let index = 0; index < 20 && (await target.count()) === 0; index++) {
    const next = dialog.getByRole('button', {
      name: 'More folders',
      exact: true,
    });
    if (await next.isDisabled()) break;
    const loaded = page.waitForResponse(
      (response) =>
        response.url().includes('/api/browse?') &&
        new URL(response.url()).searchParams.get('category') === 'folder',
    );
    await next.click();
    const rows = await (await loaded).json();
    await expect(dialog.locator('.folder-choices button')).toHaveText(
      rows.map((row: { name: string }) => `▱ ${row.name}`),
    );
  }
  await target.click();
  // Wait for both destination fetches to replace the picker before Confirm can move.
  await expect(
    dialog.getByText('Selected: ' + name, { exact: true }),
  ).toBeVisible();
}

test('desktop complete file workflows, collisions, previews, recovery and administration', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await login(page);
  await newest(page);
  const name = `stage5-${tag}.txt`;
  await uploaded(page, name, 'First original bytes');
  await expect(
    page.getByRole('button', { name: `Select ${name}`, exact: true }),
  ).toBeVisible();
  await uploaded(page, name, 'Canceled duplicate');
  await expect(
    page.getByRole('dialog', { name: 'A name already exists' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Replace', exact: true }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Cancel this file' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByLabel('Upload progress')).toHaveCount(0);
  await uploaded(page, name, 'Second copy');
  await page.getByRole('button', { name: 'Keep Both', exact: true }).click();
  await expect(
    page.getByRole('button', {
      name: `Select stage5-${tag} (1).txt`,
      exact: true,
    }),
  ).toBeVisible();
  await uploaded(page, name, 'Replacement bytes');
  await page.getByLabel('I confirm replacing the current file.').check();
  await page.getByRole('button', { name: 'Replace', exact: true }).click();
  await expect(page.getByLabel('Upload progress')).toHaveCount(0);
  await select(page, name);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download', exact: true }).click();
  const download = await downloadPromise;
  expect(fs.readFileSync((await download.path())!, 'utf8')).toBe(
    'Replacement bytes',
  );
  await action(page, 'Open');
  await expect(page.getByRole('dialog')).toContainText('Preview unavailable');
  await page
    .getByRole('button', { name: 'Close preview', exact: true })
    .click();
  await action(page, 'Rename');
  await page.getByLabel('Name', { exact: true }).fill(`renamed-${tag}.txt`);
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await select(page, `renamed-${tag}.txt`);
  await page
    .getByLabel('Custom icon', { exact: true })
    .setInputFiles(path.join(assets, 'icon.png'));
  await expect(page.getByText('Custom icon saved.')).toBeVisible();
  await expect(
    page.getByRole('complementary', { name: 'Item details' }).locator('img'),
  ).toBeVisible();
  await action(page, 'Remove icon');
  await expect(
    page.getByRole('button', { name: 'Remove icon', exact: true }),
  ).toHaveCount(0);
  await menuClick(page, 'New folder');
  await page.getByLabel('Folder name').fill(`Folder-${tag}`);
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await select(page, `renamed-${tag}.txt`);
  await action(page, 'Move');
  await chooseDestination(page, `Folder-${tag}`);
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await select(page, `Folder-${tag}`);
  await action(page, 'Open');
  await expect(
    page.getByRole('heading', { name: `Folder-${tag}`, exact: true }),
  ).toBeVisible();
  await select(page, `renamed-${tag}.txt`);
  await action(page, 'Move to Recycle Bin');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Cancel', exact: true })
    .click();
  await expect(
    page.getByRole('button', {
      name: `Select renamed-${tag}.txt`,
      exact: true,
    }),
  ).toBeVisible();
  await action(page, 'Move to Recycle Bin');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await menuClick(page, '♧ Recycle Bin');
  await select(page, `renamed-${tag}.txt`);
  await action(page, 'Restore');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await menuClick(page, '▱ All files');
  await search(page, `renamed-${tag}`);
  await select(page, `renamed-${tag}.txt`);
  await action(page, 'Move to Recycle Bin');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await menuClick(page, '♧ Recycle Bin');
  await select(page, `renamed-${tag}.txt`);
  await action(page, 'Delete permanently');
  await expect(
    page
      .getByRole('button', { name: 'Delete permanently', exact: true })
      .last(),
  ).toBeDisabled();
  await page.getByLabel('I understand and confirm permanent deletion.').check();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Delete permanently', exact: true })
    .click();
  await expect(
    page.getByRole('button', {
      name: `Select renamed-${tag}.txt`,
      exact: true,
    }),
  ).toHaveCount(0);
  // Recover the original replacement bytes from the retained recovery item.
  await select(page, name);
  // Trash details intentionally offer restoration; restore first to regain authenticated download.
  await action(page, 'Restore');
  await page.getByLabel('Keep both if a name already exists').check();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await menuClick(page, '▱ All files');
  await page.getByText('Filters & sorting', { exact: true }).click();
  await page
    .getByRole('button', { name: 'Reset filters', exact: true })
    .click();
  await select(page, name);
  const recovered = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download', exact: true }).click();
  expect(fs.readFileSync((await (await recovered).path())!, 'utf8')).toBe(
    'First original bytes',
  );
  await search(page, '');
  await newest(page);
  await page.getByLabel('Choose files to upload').setInputFiles(
    ['scene.png', 'document.pdf', 'clip.webm'].map((name) => ({
      name: name.replace('.', `-${tag}.`),
      mimeType: 'application/octet-stream',
      buffer: fs.readFileSync(path.join(assets, name)),
    })),
  );
  await expect(page.getByLabel('Upload progress')).toHaveCount(0);
  await select(page, `scene-${tag}.png`);
  await action(page, 'Open');
  await expect(
    page.getByRole('dialog').getByRole('img', { name: `scene-${tag}.png` }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Close preview', exact: true })
    .click();
  await select(page, `document-${tag}.pdf`);
  await action(page, 'Open');
  await expect(
    page
      .getByRole('dialog')
      .getByRole('img', { name: `document-${tag}.pdf, page 1` }),
  ).toBeVisible();
  await expect(
    page.getByRole('dialog').getByText('Preparing page…'),
  ).toHaveCount(0);
  await expect(page.getByRole('dialog').getByRole('alert')).toHaveCount(0);
  expect(
    await page.evaluate(
      () =>
        (globalThis as typeof globalThis & { stage5PdfExecuted?: boolean })
          .stage5PdfExecuted,
    ),
  ).toBeUndefined();
  await page.getByRole('button', { name: 'Next page', exact: true }).click();
  await expect(
    page
      .getByRole('dialog')
      .getByRole('img', { name: `document-${tag}.pdf, page 2` }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Close preview', exact: true })
    .click();
  await select(page, `clip-${tag}.webm`);
  await action(page, 'Open');
  await expect(page.getByRole('dialog').locator('video')).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator('dialog video')
        .evaluate((video: HTMLVideoElement) => video.readyState),
    )
    .toBeGreaterThan(0);
  await page
    .getByRole('button', { name: 'Close preview', exact: true })
    .click();
  await menuClick(page, '◷ Activity');
  await expect(
    page.getByRole('heading', { name: 'Activity history' }),
  ).toBeVisible();
  await expect(page.getByText('Opening your space…')).toHaveCount(0);
  await menuClick(page, '◇ Administration');
  await expect(
    page.getByRole('heading', { name: 'Storage overview' }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'Your circle' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Create invitation', exact: true })
    .click();
  await expect(
    page.getByLabel('Private invitation link · shown once'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Done', exact: true }).click();
  await page
    .getByRole('button', { name: 'Revoke', exact: true })
    .first()
    .click();
  await expect(
    page.getByText('Revoked', { exact: true }).first(),
  ).toBeVisible();
  await menuClick(page, '▱ All files');
  await menuClick(page, '☾ Dark mode');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await menuClick(page, '☀ Light mode');
  await page.screenshot({
    path: path.join(evidence, 'desktop.png'),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test('invited member sees shared files, icon rejection and server-side administrator isolation', async ({
  page,
}) => {
  const memberPath = path.join(root, '.cache/stage5-e2e-member.json');
  let member = fs.existsSync(memberPath)
    ? JSON.parse(fs.readFileSync(memberPath, 'utf8'))
    : null;
  if (!member || member.project !== fixture.project) {
    await login(page);
    await menuClick(page, '◇ Administration');
    await page
      .getByRole('button', { name: 'Create invitation', exact: true })
      .click();
    const link = await page
      .getByLabel('Private invitation link · shown once')
      .inputValue();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await menuClick(page, 'Sign out');
    member = {
      project: fixture.project,
      email: `member-stage5-${tag}@example.net`,
      password: `Synthetic UI ${randomUUID()}!`,
    };
    // Only synthetic local credentials, ignored by Git, allow safe test reruns without resetting users.
    fs.writeFileSync(memberPath, JSON.stringify(member));
    await page.goto(link);
    await page.getByLabel('Email address', { exact: true }).fill(member.email);
    await page
      .getByLabel('Choose a password', { exact: true })
      .fill(member.password);
    await page
      .getByRole('button', { name: 'Create account', exact: true })
      .click();
    await expect(
      page.getByRole('heading', { name: 'All files', exact: true }),
    ).toBeVisible();
  } else await login(page, member.email, member.password);
  await openMenu(page);
  await expect(
    page.getByRole('button', { name: '◇ Administration', exact: true }),
  ).toHaveCount(0);
  await closeMenu(page);
  for (const route of [
    '/api/admin/users',
    '/api/admin/invitations',
    '/api/admin/activity',
    '/api/admin/storage',
    '/api/admin/trash',
  ])
    expect((await page.request.get(route)).status()).toBe(403);
  const name = `member-${tag}.txt`;
  await uploaded(page, name, 'Member file');
  await select(page, name);
  await page.getByLabel('Custom icon', { exact: true }).setInputFiles({
    name: 'unsafe.png',
    mimeType: 'image/png',
    buffer: Buffer.from('<svg><script>alert(1)</script></svg>'),
  });
  await expect(page.getByRole('alert')).toContainText('valid PNG');
  await expect(
    page.getByRole('button', { name: 'Remove icon', exact: true }),
  ).toHaveCount(0);
  await action(page, 'Move to Recycle Bin');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await menuClick(page, '♧ Recycle Bin');
  await select(page, name);
  await expect(
    page.getByRole('button', { name: 'Restore', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Delete permanently', exact: true }),
  ).toHaveCount(0);
  await page.screenshot({
    path: path.join(evidence, 'member-trash.png'),
    fullPage: true,
  });
  await menuClick(page, 'Sign out');
  expect((await page.request.get('/api/browse')).status()).toBe(401);
});

test('responsive tablet/mobile, keyboard dialogs, filters, loading and connection recovery', async ({
  page,
}) => {
  await login(page);
  await page.setViewportSize({ width: 820, height: 1180 });
  await expect(
    page.getByRole('heading', { name: 'All files', exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(evidence, 'tablet.png'),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await closeMenu(page);
  await expect(
    page.getByRole('button', { name: 'Open menu', exact: true }),
  ).toBeVisible();
  await openMenu(page);
  await menuClick(page, 'New folder');
  await expect(page.getByLabel('Folder name')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(
    page.getByRole('button', { name: 'Close dialog' }),
  ).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Open menu', exact: true }),
  ).toBeFocused();
  await search(page, 'no-matching-file-stage5');
  await expect(
    page.getByRole('heading', { name: 'No matching files' }),
  ).toBeVisible();
  await page.getByText('Filters & sorting', { exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Type', exact: true })
    .selectOption('image');
  await page
    .getByRole('button', { name: 'Reset filters', exact: true })
    .click();
  await page.route('**/api/browse?**', (route) => route.abort());
  await menuClick(page, 'Refresh files');
  await expect(page.getByRole('alert')).toContainText('unavailable');
  await page.unroute('**/api/browse?**');
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveCount(0);
  const touchName = `touch-${tag}.png`;
  await page.getByLabel('Choose files to upload').setInputFiles({
    name: touchName,
    mimeType: 'image/png',
    buffer: fs.readFileSync(path.join(assets, 'scene.png')),
  });
  await search(page, touchName);
  await page
    .getByRole('button', { name: `Select ${touchName}`, exact: true })
    .tap();
  await page
    .getByRole('complementary', { name: 'Item details' })
    .getByRole('button', { name: 'Open', exact: true })
    .tap();
  await expect(
    page.getByRole('dialog').getByRole('img', { name: touchName }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Close preview', exact: true }).tap();
  await page
    .getByRole('button', { name: 'Close details', exact: true })
    .click();
  await search(page, '');
  await closeMenu(page);
  await page.screenshot({
    path: path.join(evidence, 'mobile.png'),
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test('pagination, server sorting, dropped files and both storage warning levels', async ({
  page,
}) => {
  await login(page);
  const folderName = `Pagination-${tag}`;
  await menuClick(page, 'New folder');
  await page.getByLabel('Folder name').fill(folderName);
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  const lookup = await page.request.get(`/api/collisions?name=${folderName}`);
  const parent = (await lookup.json()).id;
  const codes = await page.evaluate(async (parent_id) => {
    const me = await (await fetch('/api/auth/me')).json();
    const csrf =
      document.cookie
        .split(';')
        .map((value) => value.trim())
        .find((value) => value.startsWith(me.csrf_cookie + '='))
        ?.slice(me.csrf_cookie.length + 1) ?? '';
    const results = [];
    for (let index = 0; index < 26; index++)
      results.push(
        (
          await fetch('/api/folders', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': csrf,
            },
            body: JSON.stringify({
              parent_id,
              name: `Child-${String(index).padStart(2, '0')}`,
            }),
          })
        ).status,
      );
    return results;
  }, parent);
  expect(codes.every((code) => code === 201)).toBe(true);
  await select(page, folderName);
  await action(page, 'Open');
  await expect(page.getByLabel('Files and folders').locator('li')).toHaveCount(
    24,
  );
  await page.getByRole('button', { name: 'Next', exact: true }).click();
  await expect(page.getByLabel('Files and folders').locator('li')).toHaveCount(
    2,
  );
  await expect(
    page.getByRole('button', { name: 'Next', exact: true }),
  ).toBeDisabled();
  await page.getByRole('button', { name: 'Previous', exact: true }).click();
  await page.getByText('Filters & sorting', { exact: true }).click();
  await page
    .getByRole('combobox', { name: 'Order', exact: true })
    .selectOption('desc');
  await expect(
    page.getByLabel('Files and folders').locator('li').first(),
  ).toContainText('Child-25');
  await page
    .getByRole('combobox', { name: 'Sort by', exact: true })
    .selectOption('date');
  await expect(
    page.getByLabel('Files and folders').locator('li').first(),
  ).toContainText('Child-25');
  await page
    .getByRole('combobox', { name: 'Type', exact: true })
    .selectOption('pdf');
  await expect(
    page.getByRole('heading', { name: 'No matching files' }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Reset filters', exact: true })
    .click();
  const data = await page.evaluateHandle(() => {
    const transfer = new DataTransfer();
    transfer.items.add(
      new File([new Uint8Array([1, 2, 3])], '000-dropped.bin', {
        type: 'application/octet-stream',
      }),
    );
    return transfer;
  });
  await page
    .locator('.file-main')
    .dispatchEvent('drop', { dataTransfer: data });
  await expect(
    page.getByRole('button', { name: 'Select 000-dropped.bin', exact: true }),
  ).toBeVisible();
  await data.dispose();
  const dropped = await (
    await page.request.get(
      `/api/collisions?parent_id=${parent}&name=000-dropped.bin`,
    )
  ).json();
  await select(page, '000-dropped.bin');
  await action(page, 'Rename');
  const changed = await page.evaluate(async (item) => {
    const me = await (await fetch('/api/auth/me')).json();
    const csrf =
      document.cookie
        .split(';')
        .map((value) => value.trim())
        .find((value) => value.startsWith(me.csrf_cookie + '='))
        ?.slice(me.csrf_cookie.length + 1) ?? '';
    return (
      await fetch(`/api/items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({
          expected_revision: item.revision,
          name: '000-externally-renamed.bin',
        }),
      })
    ).status;
  }, dropped);
  expect(changed).toBe(200);
  await page.getByLabel('Name', { exact: true }).fill('000-stale-retry.bin');
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Confirm', exact: true })
    .click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText(
    'changed',
  );
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Cancel', exact: true })
    .click();
  await menuClick(page, 'Refresh files');
  await expect(
    page.getByRole('button', {
      name: 'Select 000-externally-renamed.bin',
      exact: true,
    }),
  ).toBeVisible();
  await page.route('**/api/uploads', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await route.abort().catch(() => {});
  });
  await uploaded(page, `canceled-${tag}.txt`, 'Synthetic canceled upload');
  await expect(page.getByLabel('Upload progress')).toBeVisible();
  await page
    .getByRole('button', { name: 'Cancel upload', exact: true })
    .click();
  await expect(page.getByLabel('Upload progress')).toHaveCount(0);
  await expect(page.getByRole('alert')).toContainText('canceled');
  await page.unroute('**/api/uploads');
  for (const percent of [80, 90]) {
    await page.route('**/api/storage', (route) =>
      route.fulfill({
        json: {
          used_bytes: percent * 10_000_000,
          reserved_bytes: 0,
          pool_bytes: 1_000_000_000,
          available_bytes: (100 - percent) * 10_000_000,
          warning_percent: percent,
        },
      }),
    );
    await menuClick(page, 'Refresh files');
    await expect(page.locator('.menu-warning')).toBeVisible();
    await openMenu(page);
    await expect(
      page.getByText(`Storage is at least ${percent}% full.`, { exact: true }),
    ).toBeVisible();
    await closeMenu(page);
    await page.unroute('**/api/storage');
  }
  await menuClick(page, 'Refresh files');
  await expect(page.getByText('Storage is at least 90% full.')).toHaveCount(0);
});

test('administrator can inspect and retry an already-approved pending deletion', async ({
  page,
}) => {
  await login(page);
  let pending = true;
  const id = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';
  const job = {
    id,
    target_id: 'aaaaaaaa-1111-4222-8333-eeeeeeeeeeee',
    state: 'pending',
    last_error: 'storage_unavailable',
    item_count: 2,
    created_at: '2026-10-22T10:00:00Z',
    completed_at: null,
  };
  // Presentation contract only: actual partial-unlink/role/CSRF/retry is tested on PostgreSQL/Linux.
  await page.route('**/api/admin/deletions?**', (route) =>
    route.fulfill({ json: pending ? [job] : [] }),
  );
  await page.route(`**/api/admin/deletions/${id}/retry`, (route) => {
    expect(route.request().method()).toBe('POST');
    expect(route.request().postDataJSON()).toEqual({});
    pending = false;
    return route.fulfill({
      json: {
        ...job,
        state: 'complete',
        last_error: null,
        completed_at: '2026-10-22T10:01:00Z',
      },
    });
  });
  await menuClick(page, '◇ Administration');
  await expect(
    page.getByRole('heading', { name: 'Pending deletions' }),
  ).toBeVisible();
  await expect(
    page.getByText('Storage unavailable', { exact: false }),
  ).toBeVisible();
  await page
    .getByRole('button', { name: 'Retry approved deletion', exact: true })
    .click();
  await expect(
    page.getByText('Approved deletion completed.', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText('No pending deletions.', { exact: true }),
  ).toBeVisible();
});

test('optional upload icon, grid view and dark visual smoke', async ({
  page,
}) => {
  await login(page);
  await openMenu(page);
  await page.getByText('Optional upload icon', { exact: true }).click();
  await page
    .locator('#upload-icon')
    .setInputFiles(path.join(assets, 'icon.png'));
  const name = `icon-upload-${tag}.bin`;
  await uploaded(page, name, 'Optional icon upload fixture');
  await expect(page.getByLabel('Upload progress')).toHaveCount(0);
  await search(page, name);
  await expect(
    page
      .getByRole('button', { name: `Select ${name}`, exact: true })
      .locator('img'),
  ).toBeVisible();
  await openMenu(page);
  const options = page.locator('details.upload-options');
  if ((await options.getAttribute('open')) === null)
    await options.locator('summary').click();
  await page.getByRole('button', { name: 'Clear icon', exact: true }).click();
  await expect(page.locator('#upload-icon')).toHaveValue('');
  await closeMenu(page);
  await page
    .getByRole('button', { name: 'Switch to grid view', exact: true })
    .click();
  await expect(page.locator('.file-grid')).toBeVisible();
  await select(page, name);
  await menuClick(page, '☾ Dark mode');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.screenshot({
    path: path.join(evidence, 'grid-dark.png'),
    fullPage: true,
  });
  await menuClick(page, '☀ Light mode');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});
