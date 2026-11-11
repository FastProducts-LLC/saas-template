import { expect, test } from "@playwright/test";

import { seedConsent } from "./helpers/consent";

// Public pages render with their page-root testids and key nav works.
test.describe("public pages", () => {
  test.beforeEach(async ({ context }) => {
    await seedConsent(context);
  });

  test("homepage renders with marketing chrome", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("home-page")).toBeVisible();
    await expect(page.getByTestId("marketing-header")).toBeVisible();
    await expect(page.getByTestId("marketing-footer")).toBeVisible();
  });

  test("header login link reaches the login page", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("marketing-header-login-link").click();
    await expect(page.getByTestId("login-page")).toBeVisible();
    await expect(page.getByTestId("login-email-input")).toBeVisible();
  });

  test("terms and privacy pages render", async ({ page }) => {
    await page.goto("/terms");
    await expect(page.getByTestId("terms-page")).toBeVisible();
    await page.goto("/privacy");
    await expect(page.getByTestId("privacy-page")).toBeVisible();
  });

  test("pricing page shows credit packs", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByTestId("pricing-page")).toBeVisible();
    await expect(page.getByTestId("pricing-pack").first()).toBeVisible();
  });

  test("unknown route shows the 404 page", async ({ page }) => {
    await page.goto("/definitely-not-a-page");
    await expect(page.getByTestId("not-found-page")).toBeVisible();
    await expect(page.getByTestId("not-found-home-link")).toBeVisible();
  });
});
