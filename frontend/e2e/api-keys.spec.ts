import { expect, test } from "./helpers/fixtures";

// Create → reveal secret → dismiss → revoke, all against the shared org.
test.describe.serial("api keys", () => {
  const keyName = `e2e-key-${Date.now()}`;

  test("create a key", async ({ authedPage: page }) => {
    await page.goto("/api-keys");
    await expect(page.getByTestId("api-keys-page")).toBeVisible();

    await page.getByTestId("api-keys-create-button").click();
    await expect(page.getByTestId("api-keys-create-modal")).toBeVisible();
    await page.getByTestId("api-keys-name-input").fill(keyName);
    await page.getByTestId("api-keys-create-confirm").click();

    // The raw secret is shown exactly once.
    await expect(page.getByTestId("api-keys-secret")).toBeVisible();
    await expect(page.getByTestId("api-keys-secret")).toContainText("sk_");
    await page.getByTestId("api-keys-dismiss-button").click();
    await expect(page.getByTestId("api-keys-secret")).not.toBeVisible();

    await expect(page.getByTestId("api-keys-row").filter({ hasText: keyName })).toBeVisible();
  });

  test("revoke the key", async ({ authedPage: page }) => {
    await page.goto("/api-keys");
    const row = page.getByTestId("api-keys-row").filter({ hasText: keyName });
    await expect(row).toBeVisible();

    await row.getByTestId("api-keys-revoke-button").click();
    await expect(page.getByTestId("api-keys-revoke-modal")).toBeVisible();
    await page.getByTestId("api-keys-revoke-confirm").click();
    await expect(page.getByTestId("api-keys-revoke-modal")).not.toBeVisible();
    await expect(row).not.toBeVisible();
  });
});
