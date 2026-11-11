import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import { request, type FullConfig } from "@playwright/test";

import {
  loginViaApi,
  registerUser,
  STATE_FILE,
  uniquePassword,
  uniqueUser,
  type SharedState,
} from "./helpers/accounts";
import { extractAppLink, fetchEmailHtml } from "./helpers/mailpit";

// One shared user + org per run (register is throttled at 10/hour/IP).
// Workers log in with these creds via API — see helpers/fixtures.ts.
export default async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL ?? "http://localhost:21427";

  const api = await request.newContext({ baseURL });

  // Fail fast with a useful message when the stack isn't up.
  try {
    const ping = await api.get("/", { timeout: 5_000 });
    if (!ping.ok()) throw new Error(`frontend responded ${ping.status()}`);
  } catch (err) {
    throw new Error(
      `E2E stack not reachable at ${baseURL} — start it with \`docker compose up\` ` +
        `from the repo root (frontend :21427).`,
      { cause: err },
    );
  }

  const user = uniqueUser("shared");
  const password = uniquePassword();
  await registerUser(api, user, password);

  // EMAIL_VERIFICATION_GATE=sensitive requires a verified mailbox before
  // org create — confirm via the welcome mail in Mailpit.
  const html = await fetchEmailHtml(user.email, "confirm your email");
  const link = extractAppLink(html, "/verify-email");
  // Email links carry the token in the URL fragment (kept out of server
  // logs); `?token=` is the legacy form the app still accepts.
  const url = new URL(link);
  const token =
    new URLSearchParams(url.hash.replace(/^#/, "")).get("token") ?? url.searchParams.get("token");
  if (!token) throw new Error(`no token in verification link: ${link}`);
  const verify = await api.post("/api/auth/verify-email", { data: { token } });
  if (verify.status() !== 204) {
    throw new Error(`verify-email failed: ${verify.status()} ${await verify.text()}`);
  }

  // Register returns no token — the API authorizes with a Bearer access
  // token from login (the cookie is only for refresh).
  const login = await loginViaApi(api, user.email, password);
  const { access_token } = (await login.json()) as { access_token: string };

  const orgRes = await api.post("/api/orgs", {
    headers: { Authorization: `Bearer ${access_token}` },
    data: { name: `E2E Org ${Date.now()}`, intended_use: "Automated end-to-end testing" },
  });
  if (orgRes.status() !== 201) {
    throw new Error(`org create failed: ${orgRes.status()} ${await orgRes.text()}`);
  }
  const org = (await orgRes.json()) as { id: string; name: string };

  const state: SharedState = { email: user.email, password, orgId: org.id, orgName: org.name };
  if (!existsSync(dirname(STATE_FILE))) mkdirSync(dirname(STATE_FILE), { recursive: true });
  writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));

  await api.dispose();
}
