import { defineConfig, devices } from "@playwright/test";

// E2E suite — runs against the local Docker stack (frontend :21427).
// `docker compose up` must be running first; global-setup fails fast with a
// clear message if it isn't.
//
// Rate limits shape this config (see e2e/README.md): auth endpoints are
// IP-throttled (register 10/h, login 5/min), so the suite registers exactly
// one shared user per run, logs in once per worker, and runs single-worker so
// logins never burst. If iterating locally trips a limit, run
// `e2e/reset-rate-limits.sh`.
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup",
  outputDir: "./test-results",
  workers: 1,
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:21427",
    trace: "retain-on-failure",
    testIdAttribute: "data-testid",
    // The app honors prefers-reduced-motion — skipping the gd-* entrance
    // animations keeps elements stable for clicks.
    reducedMotion: "reduce",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
