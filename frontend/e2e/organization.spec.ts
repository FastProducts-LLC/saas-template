import { expect, test } from "./helpers/fixtures";

test.describe.serial("organization management", () => {
  const inviteEmail = `e2e-invitee-${Date.now()}@example.com`;

  test("rename the organization in settings", async ({ authedPage: page }) => {
    const newName = `E2E Org renamed ${Date.now()}`;
    await page.goto("/settings");
    await expect(page.getByTestId("org-settings-page")).toBeVisible();

    await page.getByTestId("org-settings-name-input").fill(newName);
    await page.getByTestId("org-settings-rename-submit").click();
    await expect(page.getByTestId("org-settings-success")).toBeVisible();
  });

  test("invite a member and see the pending invitation", async ({ authedPage: page }) => {
    await page.goto("/members");
    await expect(page.getByTestId("members-page")).toBeVisible();

    // The owner is listed as an active member.
    await expect(page.getByTestId("members-row").first()).toBeVisible();

    await page.getByTestId("invite-email-input").fill(inviteEmail);
    await page.getByTestId("invite-submit").click();
    await expect(
      page.getByTestId("invitations-row").filter({ hasText: inviteEmail }),
    ).toBeVisible();
  });

  test("revoke the pending invitation", async ({ authedPage: page }) => {
    await page.goto("/members");
    const row = page.getByTestId("invitations-row").filter({ hasText: inviteEmail });
    await expect(row).toBeVisible();
    await row.getByTestId("invitations-revoke-button").click();
    await expect(row).not.toBeVisible();
  });
});
