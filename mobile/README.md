# MyApp Mobile

Expo (React Native + TypeScript) app for iOS and Android, integrated with the
FastAPI backend in `../backend`. Mirrors the web frontend's architecture:
feature slices with `api/{endpoints,keys,hooks}` + `model/`, a catalog-aware
API client, and TanStack Query for all server state.

## Run it

```bash
# from the repo root — the backend must be up
docker compose up --build

cd mobile
npm install
npm start          # Expo dev server; press i (iOS simulator) or a (Android emulator)
```

No API URL configuration is needed in development: the client derives the
backend address from the Expo dev-server host, so

- iOS simulator → `http://localhost:21428/api`
- Android emulator → `http://10.0.2.2:21428/api`
- physical device on the same Wi-Fi → `http://<your-LAN-IP>:21428/api`

all work out of the box. For staging/production builds set
`EXPO_PUBLIC_API_URL=https://api.example.com` (the client appends `/api`).

Sign in with the seeded dev user (`docker compose exec backend python
scripts/seed_dev.py`): `dev@example.com` and the password that script prints
(generated per checkout, kept in `backend/.dev-secrets/seed_password`).

## Checks

```bash
npm run typecheck   # tsc --noEmit
npm test            # vitest — API client unit tests (pure Node, fakes injected)
```

## How auth works on native

There is no httpOnly cookie jar in React Native, so the app uses the
backend's mobile flow: every request carries `X-Client: mobile`, which makes
`/auth/login`, `/auth/refresh`, and `/auth/change-password` return the
(rotating, single-use) refresh token in the **response body** instead of a
cookie. The client keeps the access token in memory and the refresh token in
`expo-secure-store` (Keychain / Android Keystore), refreshes once on any 401
(single-flight, so parallel 401s share one refresh), and persists the rotated
token before retrying. Web keeps the cookie flow — the body variant only
activates for mobile clients.

## Layout

```
src/
  app/                     expo-router routes
    sign-in.tsx, register.tsx, forgot-password.tsx
    (app)/                 auth-guarded Stack (native headers on detail screens)
      (tabs)/              Dashboard · Generate · Text (LLM) · Settings
      generation/[id].tsx  detail, result image, cancel/delete
      llm/[id].tsx         completion detail: response text + token accounting
      members.tsx          roster, role changes, invite/revoke (role-gated)
      api-keys.tsx         list/create (raw key shown once, copy) /revoke
      billing.tsx          credit packs → Stripe Checkout in browser, invoices, portal
      account.tsx          profile edit + GDPR analytics consent
      change-password.tsx  rotates the session; this device stays signed in
  features/<name>/         auth, organizations, credits, generations, llm,
    api/                   billing, api-keys, consent —
    model/                 endpoints.ts / keys.ts / hooks.ts + model types
    index.ts               public API — cross-feature imports go through here
  shared/
    api/                   client.ts (port of frontend shared/api), setup.ts
                           (SecureStore/crypto wiring), errorCatalog.ts +
                           enums.ts (both GENERATED)
    ui/                    theme tokens (DESIGN.md palette) + primitives
```

Stripe checkout and the customer portal open in the system browser (Stripe
pages can't be embedded); wallet, invoices, and billing account refetch
automatically when the app returns to the foreground, so completed purchases
appear without a manual refresh.

Conventions carried over from the web frontend:

- Components never touch endpoints or the query client — only domain hooks.
- Errors are never thrown manually; the client normalizes every failure into
  a catalog-aware `ApiError` (`userMessage`, `actionStep`, `fields`,
  `reference`). Global surface is the toast host; forms bind `err.fields`.
- Mutations carry an `Idempotency-Key` reused across retries.
- `errorCatalog.ts` is generated — edit `shared/errors.toml` at the repo root
  and run `python3 scripts/gen_errors.py`.

## Plans and limits

The Billing screen shows the organization's current plan and subscription
status read-only, with guidance to manage plans in the web app. There is no
native plan checkout or plan-change UI: plan purchases stay in the web flow
to avoid introducing native in-app subscription purchasing. Existing credit-pack
checkout and the general Stripe billing portal still open in the system browser.

The members and API-key screens read the entitlement snapshot, display usage
and limits, and disable creation when capacity is reached. The backend enforces
the same limits. Mobile uses `useEntitlements` and capacity helpers; the web's
`RequireEntitlement` component is not part of the native implementation.
Community profiles, avatar uploads, directory, and messaging remain web-only.
