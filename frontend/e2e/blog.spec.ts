import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { seedUiState } from "./helpers/consent";

// Blog CMS: superuser authors + publishes in /admin/blog, a logged-out visitor
// reads at /blog, unpublish hides the article again.
//
// Uses the seeded dev superuser (scripts/seed_dev.py) because the shared e2e
// account is a plain user; skips if the seed hasn't been run. The seed
// password is generated per checkout (never a committed constant): read it
// from E2E_SUPERUSER_PASSWORD or the file the seed script writes.
const SUPERUSER_EMAIL = "dev@example.com";
const SEED_PASSWORD_FILE = path.resolve(process.cwd(), "../backend/.dev-secrets/seed_password");
const SUPERUSER_PASSWORD =
  process.env.E2E_SUPERUSER_PASSWORD ??
  (existsSync(SEED_PASSWORD_FILE) ? readFileSync(SEED_PASSWORD_FILE, "utf8").trim() : "");

test.describe.serial("blog cms", () => {
  const stamp = Date.now();
  const title = `E2E Post ${stamp}`;
  const slug = `e2e-post-${stamp}`;

  test("author, publish, read logged-out, unpublish, delete", async ({ browser }) => {
    const adminContext = await browser.newContext();
    await seedUiState(adminContext);
    test.skip(
      !SUPERUSER_PASSWORD,
      "dev superuser not seeded — run: docker compose exec backend python scripts/seed_dev.py",
    );
    const login = await adminContext.request.post("/api/auth/login", {
      data: { email: SUPERUSER_EMAIL, password: SUPERUSER_PASSWORD },
    });
    test.skip(
      login.status() !== 200,
      "dev superuser not seeded — run: docker compose exec backend python scripts/seed_dev.py",
    );

    const admin = await adminContext.newPage();
    const visitorContext = await browser.newContext();
    await seedUiState(visitorContext);
    const visitor = await visitorContext.newPage();

    // --- author a draft
    await admin.goto("/admin/blog");
    await expect(admin.getByTestId("admin-blog-page")).toBeVisible();
    await admin.getByTestId("admin-blog-new-button").click();
    await expect(admin.getByTestId("admin-blog-editor-page")).toBeVisible();

    await admin.getByTestId("admin-blog-title-input").fill(title);
    await expect(admin.getByTestId("admin-blog-slug-input")).toHaveValue(slug);
    await admin.getByTestId("admin-blog-excerpt-input").fill("Written by the e2e suite.");
    await admin
      .getByTestId("admin-blog-content-input")
      .fill("## From the robots\n\nThis paragraph was typed by Playwright.");

    // Markdown preview renders the heading.
    await admin.getByTestId("admin-blog-preview-tab").click();
    await expect(
      admin.getByTestId("admin-blog-preview").getByRole("heading", { name: "From the robots" }),
    ).toBeVisible();
    await admin.getByTestId("admin-blog-write-tab").click();

    await admin.getByTestId("admin-blog-save-button").click();
    await admin.waitForURL(/\/admin\/blog\/[0-9a-f-]{36}$/);

    // --- draft is invisible publicly
    await visitor.goto(`/blog/${slug}`);
    await expect(visitor.getByTestId("blog-article-not-found")).toBeVisible();

    // --- publish
    await admin.getByTestId("admin-blog-publish-button").click();
    await expect(admin.getByTestId("admin-blog-unpublish-button")).toBeVisible();

    // --- visitor reads it
    await visitor.goto("/blog");
    await expect(visitor.getByTestId("blog-list-page")).toBeVisible();
    await visitor.getByRole("link", { name: title }).click();
    await expect(visitor.getByRole("heading", { name: title })).toBeVisible();
    await expect(visitor.getByText("This paragraph was typed by Playwright.")).toBeVisible();

    // --- unpublish hides it again
    await admin.getByTestId("admin-blog-unpublish-button").click();
    await expect(admin.getByTestId("admin-blog-publish-button")).toBeVisible();
    await visitor.goto(`/blog/${slug}`);
    await expect(visitor.getByTestId("blog-article-not-found")).toBeVisible();

    // --- cleanup: delete the post
    await admin.getByTestId("admin-blog-delete-button").click();
    await admin.getByTestId("admin-blog-confirm-delete-button").click();
    await admin.waitForURL(/\/admin\/blog$/);

    await adminContext.close();
    await visitorContext.close();
  });
});
