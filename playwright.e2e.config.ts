import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end regression for permissions / 403 and the buyer + seller flows.
 *
 * Unlike `playwright.config.ts` (which runs `npm start` with Mock enabled and can
 * only test the mock login), this config runs the real stack:
 *
 *   frontend  dev server (:8000 by default)  — dev proxy /api/v1 -> :9000
 *   backend   FastAPI (:9000)                — must be running
 *
 * `mock/` defines no `/api/v1/*` handler, so even an `npm start` server proxies
 * auth and business calls to the real FastAPI app; the assertions therefore test
 * the real RBAC, not a mock.
 *
 * Override the port with `E2E_PORT=...` when running against another instance.
 */
const PORT = Number(process.env.E2E_PORT ?? 8000);

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.e2e\.spec\.ts/,
  outputDir: './e2e-out/regression-results',
  reporter: [['list'], ['html', { outputFolder: 'e2e-out/regression-report' }]],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: `http://localhost:${PORT}`,
    locale: 'zh-CN',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 45_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `cross-env UMI_ENV=dev MOCK=none PORT=${PORT} max dev`,
    url: `http://localhost:${PORT}/user/login`,
    reuseExistingServer: true,
    timeout: 180_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
