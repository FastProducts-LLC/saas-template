import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, type APIRequestContext } from "@playwright/test";

// ESM package ("type": "module") — no __dirname global.
const here = dirname(fileURLToPath(import.meta.url));
export const STATE_FILE = join(here, "..", ".state", "shared-user.json");

export interface SharedState {
  email: string;
  password: string;
  orgId: string;
  orgName: string;
}

export interface NewUser {
  firstName: string;
  lastName: string;
  email: string;
}

export function sharedState(): SharedState {
  return JSON.parse(readFileSync(STATE_FILE, "utf8")) as SharedState;
}

// Unique per run so repeated runs never collide on the email unique index.
export function uniqueUser(tag: string): NewUser {
  const stamp = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  return {
    firstName: "E2E",
    lastName: tag,
    email: `e2e-${tag}-${stamp}@example.com`,
  };
}

export function uniquePassword(): string {
  return `E2ePass!${Date.now()}`;
}

// Register via the API (through the vite proxy, so the refresh cookie lands
// in the caller's jar). Register is throttled at 10/hour/IP — a 429 here
// means too many runs; clear counters with e2e/reset-rate-limits.sh.
export async function registerUser(api: APIRequestContext, user: NewUser, password: string) {
  const res = await api.post("/api/auth/register", {
    data: {
      first_name: user.firstName,
      last_name: user.lastName,
      email: user.email,
      password,
      password_confirmation: password,
      terms_accepted: true,
      marketing_opt_in: false,
    },
  });
  if (res.status() === 429) {
    throw new Error(
      "register rate limit hit (10/hour/IP) — run frontend/e2e/reset-rate-limits.sh and retry",
    );
  }
  expect(res.status(), await res.text()).toBe(201);
  return res;
}

// Login is throttled at 5/min/IP and a run needs ~5 logins, so back-to-back
// runs start inside the previous run's window — out-wait it rather than fail.
export async function loginViaApi(api: APIRequestContext, email: string, password: string) {
  for (let attempt = 0; ; attempt++) {
    const res = await api.post("/api/auth/login", { data: { email, password } });
    if (res.status() !== 429) {
      expect(res.status(), await res.text()).toBe(200);
      return res;
    }
    if (attempt >= 4) {
      throw new Error(
        "login still throttled after 5 attempts (5/min/IP) — run frontend/e2e/reset-rate-limits.sh",
      );
    }
    await new Promise((resolve) => setTimeout(resolve, 21_000));
  }
}
