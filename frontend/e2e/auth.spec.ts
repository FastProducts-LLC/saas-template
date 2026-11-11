import { expect, test } from "@playwright/test";

import { uniquePassword, uniqueUser } from "./helpers/accounts";
import { seedUiState } from "./helpers/consent";
import { extractAppLink, fetchEmailHtml } from "./helpers/mailpit";

// UI login that out-waits the 5/min login throttle. This spec inevitably
// brushes the limit: the run already spends logins on global-setup, the
// worker fixture, and RegisterPage's hidden auto-login.
async function uiLogin(page: import("@playwright/test").Page, email: string, password: string) {
  for (let attempt = 0; ; attempt++) {
    await page.getByTestId("login-email-input").fill(email);
    await page.getByTestId("login-password-input").fill(password);
    const [res] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/auth/login")),
      page.getByTestId("login-submit").click(),
    ]);
    if (res.status() !== 429) return;
    if (attempt >= 3) throw new Error("login still throttled after 4 attempts");
    await page.waitForTimeout(21_000);
  }
}

// Full auth journeys for a dedicated user (separate from the shared fixture
// user so logout/reset here can't break other specs). Serial: later tests
// build on the account created in the first one.
test.describe.serial("auth journey", () => {
  const user = uniqueUser("auth");
  const password = uniquePassword();
  const newPassword = `${uniquePassword()}b`;

  test.beforeEach(async ({ context }) => {
    await seedUiState(context);
  });

  test("register via UI, verify email, then create org", async ({ page }) => {
    await page.goto("/register");
    await page.getByTestId("register-first-name-input").fill(user.firstName);
    await page.getByTestId("register-last-name-input").fill(user.lastName);
    await page.getByTestId("register-email-input").fill(user.email);
    await page.getByTestId("register-password-input").fill(password);
    await page.getByTestId("register-confirm-password-input").fill(password);
    await page.getByTestId("register-terms-checkbox").check();
    await page.getByTestId("register-submit").click();

    // New users have no org yet — AppLayout bounces them to /orgs/new.
    await expect(page.getByTestId("create-org-page")).toBeVisible();

    // EMAIL_VERIFICATION_GATE=sensitive blocks org create until the mailbox
    // is confirmed — open the link from Mailpit first.
    const html = await fetchEmailHtml(user.email, "confirm your email");
    const link = extractAppLink(html, "/verify-email");
    await page.goto(link);
    await expect(page.getByTestId("verify-email-success")).toBeVisible();

    await page.goto("/orgs/new");
    await expect(page.getByTestId("create-org-page")).toBeVisible();

    // The form remounts once while the fresh session's context settles, which
    // can wipe values filled too early — required-field validation then
    // silently blocks the submit. Retry the whole fill→submit→landed cycle.
    const orgName = `Auth Org ${Date.now()}`;
    await expect(async () => {
      await page.getByTestId("create-org-name-input").fill(orgName);
      await page.getByTestId("create-org-intended-use-input").fill("E2E auth journey");
      await page.getByTestId("create-org-submit").click();
      await expect(page.getByTestId("dashboard-page")).toBeVisible({ timeout: 5_000 });
    }).toPass({ timeout: 30_000 });
  });

  test("email already verified stays verified after a second link click", async ({ page }) => {
    // Registration sent "Welcome to <app> — confirm your email"; a second
    // click must remain idempotent.
    const html = await fetchEmailHtml(user.email, "confirm your email");
    const link = extractAppLink(html, "/verify-email");
    await page.goto(link);
    await expect(page.getByTestId("verify-email-success")).toBeVisible();
  });

  test("wrong password shows an inline error", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-email-input").fill(user.email);
    await page.getByTestId("login-password-input").fill("Wrong-password-1");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("login-error")).toBeVisible();
  });

  test("login and logout round-trip", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/login");
    await uiLogin(page, user.email, password);
    await expect(page.getByTestId("dashboard-page")).toBeVisible();

    await page.getByTestId("nav-logout-button").click();
    await expect(page.getByTestId("dashboard-page")).not.toBeVisible();

    // Session is really gone: a protected route bounces to login.
    await page.goto("/dashboard");
    await expect(page.getByTestId("login-page")).toBeVisible();
  });

  test("password reset via emailed link", async ({ page }) => {
    // The final assertion may need to out-wait the 5/min login window.
    test.setTimeout(120_000);
    await page.goto("/forgot-password");
    await page.getByTestId("forgot-password-email-input").fill(user.email);
    await page.getByTestId("forgot-password-submit").click();
    await expect(page.getByTestId("forgot-password-success")).toBeVisible();

    const html = await fetchEmailHtml(user.email, "Reset your password");
    const link = extractAppLink(html, "/reset-password");
    await page.goto(link);
    await page.getByTestId("reset-password-password-input").fill(newPassword);
    await page.getByTestId("reset-password-confirm-password-input").fill(newPassword);
    await page.getByTestId("reset-password-submit").click();
    await expect(page.getByTestId("reset-password-success")).toBeVisible();

    // The new password authenticates. Asserted via API because this is the
    // 5th login of the run — a 429 from the 5/min window may need to be
    // out-waited, and the wide polling interval avoids re-filling it.
    await expect
      .poll(
        async () => {
          const res = await page.request.post("/api/auth/login", {
            data: { email: user.email, password: newPassword },
          });
          return res.status();
        },
        {
          message: "login with the new password to succeed",
          timeout: 90_000,
          intervals: [1_000, 15_000],
        },
      )
      .toBe(200);
  });
});
