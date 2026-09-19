import { defineConfig, devices } from "@playwright/test";

/**
 * `@critical` end-to-end tests (M4). Two modes:
 * - default (CI): the static export in `out/`, built with NEXT_PUBLIC_API_URL=http://api.e2e.test and
 *   served locally; every API call is answered from `e2e/fixtures` (recorded responses) by `page.route`.
 * - E2E_BASE_URL set: the same golden path against a deployed site and its real API, no mocks.
 */
const live = Boolean(process.env.E2E_BASE_URL);

export default defineConfig({
  testDir: "e2e",
  timeout: live ? 120_000 : 30_000,
  expect: { timeout: live ? 60_000 : 5_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["github"]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:4173",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: live
    ? undefined
    : { command: "node e2e/serve.mjs", url: "http://127.0.0.1:4173/", reuseExistingServer: !process.env.CI },
});
