import { test as base, type BrowserContext, type Page } from "@playwright/test";

import { loginViaApi, sharedState, type SharedState } from "./accounts";
import { seedUiState } from "./consent";

interface AuthedFixtures {
  authedPage: Page;
  shared: SharedState;
}

interface AuthedWorkerFixtures {
  authedContext: BrowserContext;
}

// Authenticated tests share ONE browser context per worker. The session lives
// in a rotating single-use httpOnly refresh cookie, so a persisted
// storageState file would go stale after its first use — a live cookie jar is
// the only shape that survives rotation. It also means one login per worker,
// which keeps us under the 5/min login throttle.
export const test = base.extend<AuthedFixtures, AuthedWorkerFixtures>({
  authedContext: [
    async ({ browser }, use) => {
      const context = await browser.newContext();
      await seedUiState(context);
      const creds = sharedState();
      await loginViaApi(context.request, creds.email, creds.password);
      await use(context);
      await context.close();
    },
    { scope: "worker" },
  ],

  authedPage: async ({ authedContext }, use) => {
    const page = await authedContext.newPage();
    await use(page);
    await page.close();
  },

  // eslint-disable-next-line no-empty-pattern -- Playwright fixtures require a destructuring pattern
  shared: async ({}, use) => {
    await use(sharedState());
  },
});

export { expect } from "@playwright/test";
