import { expect, test } from "./helpers/fixtures";

test.describe("profile", () => {
  test("update display name", async ({ authedPage: page }) => {
    await page.goto("/profile");
    await expect(page.getByTestId("profile-page")).toBeVisible();

    await page.getByTestId("profile-first-name-input").fill("E2E");
    await page.getByTestId("profile-last-name-input").fill(`Renamed${Date.now() % 1000}`);
    await page.getByTestId("profile-name-submit").click();
    await expect(page.getByTestId("profile-name-success")).toBeVisible();
  });

  test("toggle marketing opt-in", async ({ authedPage: page }) => {
    await page.goto("/profile");
    const checkbox = page.getByTestId("profile-marketing-checkbox");
    await expect(checkbox).toBeVisible();

    // Controlled input: the checked state flips only after the server
    // mutation resolves, so click + wait rather than setChecked.
    const before = await checkbox.isChecked();
    await checkbox.click();
    await expect(checkbox).toBeChecked({ checked: !before });

    // Persisted server-side: survives a reload. (No restore needed — the
    // shared user is created fresh each run.)
    await page.reload();
    await expect(page.getByTestId("profile-marketing-checkbox")).toBeChecked({
      checked: !before,
    });
  });
});
