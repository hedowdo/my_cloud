import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120000,
  expect: { timeout: 15000 },
  outputDir: path.resolve(
    import.meta.dirname,
    '../.local/stage5-browser/results',
  ),
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8080',
    channel: 'chrome',
    headless: true,
    hasTouch: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
});
