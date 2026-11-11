# E2E tests (Playwright)

Browser tests against the real local stack — no mocks. Selectors come from the
`data-testid` contract in `frontend/TESTING.md`.

## Running

```bash
docker compose up          # from the repo root; the suite needs the full stack
cd frontend
npm run test:e2e           # headless
npm run test:e2e:ui        # Playwright UI mode
npm run test:e2e:headed    # watch the browser
```

First-time setup: `npx playwright install chromium`.

## How the suite handles auth + rate limits

The API throttles per IP: **register 10/hour, login 5/minute,
forgot-password 5/hour**. The suite is built around that:

- `global-setup.ts` registers **one shared user + org per run**; authenticated
  specs reuse it through the `authedPage` fixture (`helpers/fixtures.ts`).
- The session is a **rotating single-use refresh cookie**, so a persisted
  `storageState` file would go stale after first use. Instead each worker
  keeps one live browser context (one API login per worker).
- `auth.spec.ts` registers a second, dedicated user for the register / verify /
  reset journeys so logout and password changes can't break other specs.
- Login helpers tolerate 429s by out-waiting the window — back-to-back runs
  pass but the second run can take ~2 minutes instead of ~20 seconds.
- Each run consumes 2 registrations → after ~5 runs in an hour, clear the
  counters: `./e2e/reset-rate-limits.sh` (deletes only `LIMITS:*` keys in
  Valkey).

## Conventions

- New tests that aren't about the cookie banner or onboarding tour should call
  `seedUiState(context)` (or use the `authedPage` fixture, which does it) so
  overlays never intercept clicks.
- Test users/orgs are timestamp-unique and accumulate in the local DB — no
  cleanup is attempted. `docker compose down -v` resets everything.
- The shared org has **zero credits** (no free grants). Credit-consuming
  flows would need a superuser credit adjustment first — not covered yet.
- Emails are read from Mailpit's API (`helpers/mailpit.ts`), filtered by
  recipient + subject.
