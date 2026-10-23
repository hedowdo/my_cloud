import { type Page } from '@playwright/test';
export async function openMenu(page: Page) {
  if (
    (await page
      .getByRole('dialog', { name: 'Navigation and tools' })
      .count()) === 0
  )
    await page.getByRole('button', { name: 'Open menu', exact: true }).click();
}
export async function closeMenu(page: Page) {
  if (await page.getByRole('dialog', { name: 'Navigation and tools' }).count())
    await page.getByRole('button', { name: 'Close menu', exact: true }).click();
}
export async function menuClick(page: Page, name: string) {
  await openMenu(page);
  await page.getByRole('button', { name, exact: true }).click();
  if (name !== 'Sign out') await closeMenu(page);
}
export async function pan(page: Page, direction: string) {
  const more = page.locator('.spatial-more');
  if ((await more.getAttribute('open')) === null)
    await more.locator('summary').click();
  await page
    .getByRole('button', { name: `Pan ${direction}`, exact: true })
    .click();
  await more.locator('summary').click();
}

export async function recenter(page: Page) {
  const more = page.locator('.spatial-more');
  if ((await more.getAttribute('open')) === null)
    await more.locator('summary').click();
  await page.getByRole('button', { name: 'Recenter', exact: true }).click();
  await more.locator('summary').click();
}
