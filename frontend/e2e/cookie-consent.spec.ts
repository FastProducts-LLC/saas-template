import { expect, test } from "@playwright/test";

// The one spec that starts WITHOUT pre-seeded consent — it tests the banner
// itself. Each test gets a fresh context (no persisted decision).
test.describe("cookie consent", () => {
  test("banner shows on first visit and reject persists", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("cookie-banner")).toBeVisible();

    await page.getByTestId("cookie-reject-button").click();
    await expect(page.getByTestId("cookie-banner")).not.toBeVisible();

    await page.reload();
    await expect(page.getByTestId("home-page")).toBeVisible();
    await expect(page.getByTestId("cookie-banner")).not.toBeVisible();
  });

  test("accept all persists across reloads", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("cookie-accept-all-button").click();
    await expect(page.getByTestId("cookie-banner")).not.toBeVisible();

    await page.reload();
    await expect(page.getByTestId("home-page")).toBeVisible();
    await expect(page.getByTestId("cookie-banner")).not.toBeVisible();
  });

  test("customize opens preferences and saves a granular choice", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("cookie-preferences-button").click();
    await expect(page.getByTestId("cookie-preferences-modal")).toBeVisible();

    // Essential is always on and locked.
    await expect(page.getByTestId("cookie-essential-checkbox")).toBeChecked();
    await expect(page.getByTestId("cookie-essential-checkbox")).toBeDisabled();

    await page.getByTestId("cookie-analytics-checkbox").check();
    await page.getByTestId("cookie-save-button").click();
    await expect(page.getByTestId("cookie-preferences-modal")).not.toBeVisible();
    await expect(page.getByTestId("cookie-banner")).not.toBeVisible();
  });

  test("footer cookie settings reopens preferences after deciding", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("cookie-reject-button").click();

    await page.getByTestId("marketing-footer-cookie-settings-button").scrollIntoViewIfNeeded();
    await page.getByTestId("marketing-footer-cookie-settings-button").click();
    await expect(page.getByTestId("cookie-preferences-modal")).toBeVisible();
  });
});
