# Customization Guide — Rebranding the Template into a New App

This template ships as **"SaaS Template"** with placeholder copy, the
"Carbon & Lime" theme (see `DESIGN.md`), and placeholder legal/billing config. This
guide is the complete checklist for turning a fresh copy into a named product.
Work top-to-bottom; nothing here requires touching the domain logic in
`backend/app/domains/` unless you're adding features.

> **Conventions used below**
> - `myapp` = your chosen app **slug** (lowercase, no spaces). Pick it once —
>   it drives compose project names, image repos, deploy files, and
>   DigitalOcean resource names. The deploy artifacts already use `myapp` as
>   their placeholder slug.
> - "Brand string" = the visible product name, e.g. `Acme Hooks`.
> - All paths are relative to the repo root.

---

## 0. Quick start (the 5-minute rebrand)

| # | What | How |
|---|------|-----|
| 1 | Identity, deploy settings, legal identity, palette + font families | Edit `[brand]`, `[deploy]`, `[legal]`, and `[theme.*]` in `shared/brand.toml` (see §1, §3, §4) |
| 2 | Apply the rebrand + regenerate | `python3 scripts/rebrand.py` — reads the toml, renames deploy artifacts, rewrites slug/domain/GHCR owner/ports, and runs the brand generator; preview with `python3 scripts/rebrand.py --dry-run` |
| 3 | Landing + auth-panel copy | Rewrite `HOME_CONTENT` and `AUTH_PANEL_CONTENT` in `frontend/src/shared/content/marketing.ts` |
| 4 | Manual assets + fonts | Swap `frontend/public/favicon.svg`, update font packages/imports in `frontend/src/main.tsx`, review Android adaptive-icon color in `mobile/app.json`, and record visual decisions in `DESIGN.md` |
| 5 | Policy knobs (password length, API-key prefix, field limits, page sizes, rate limits) | Edit `shared/policy.toml`, run `python3 scripts/gen_policy.py` |
| 6 | Legal review | Review `frontend/src/features/legal/TERMS_OF_SERVICE.md` and `frontend/src/features/legal/PRIVACY_POLICY.md` with counsel; identity placeholders resolve from the toml at render time |
| 7 | Env values (emails, secrets) | rebrand.py sets the brand name in `.env.example` and `env/<slug>.env.example` (`APP_NAME` and placeholder `EMAIL_FROM_NAME`); populate real `.env` / `env/<slug>.env` files yourself — `python3 scripts/check_env_examples.py` verifies example coverage |
| 8 | Stripe products/prices for credit packs, community memberships, and org plans | `docker compose exec backend python scripts/stripe_sync.py` — creates them from the catalog and prints the `STRIPE_PRICE_CREDITS_*`, `STRIPE_PRICE_COMMUNITY_*`, and `STRIPE_PRICE_PLAN_*` env lines |
| 9 | Public API docs | `frontend/public/docs/api.md` — rebrand.py already swapped the domain and API docs title from `[brand].name`; `docs/api.md` is a pointer, not a second copy |

CI runs `--check` for every generator (plus the env-example check) in the
backend test job, so a half-done rebrand fails the build instead of shipping.

**Sanity sweep** — `rebrand.py` runs one automatically; to re-run by hand:

```bash
grep -rnE 'SaaS Template|COMPANY LEGAL NAME|your-domain\.com|your-org|myapp' \
  shared/brand.toml frontend/index.html frontend/src frontend/public/docs/api.md \
  backend/app mobile/src mobile/app.json docker-compose*.yml .env*.example \
  env/ caddy.d/ .github/workflows/ deploy.sh setup-platform.sh scripts/rollout.sh
```

Review matches: tests may intentionally retain template fixtures. This sweep
excludes convention docs such as this guide, which deliberately use `myapp`
and `your-domain.com`.

---

## 1. Branding & naming

### 1.1 Brand constants (one source, generated everywhere)
- `shared/brand.toml` is the single source of truth. `[brand]` holds `name`,
  `legal_name`, `tagline`, `description`, and `support_email`; `[deploy]`
  holds `slug`, `domain`, `ghcr_org`, and `port_base`. Set the support mailbox
  explicitly if needed: rebrand.py updates its domain only when it still ends
  in `@your-domain.com`, preserving custom addresses.
- `python3 scripts/gen_brand.py` generates identity constants in
  `frontend/src/shared/lib/brand.ts`, `mobile/src/shared/lib/brand.ts`, and
  `backend/app/core/brand.py`, including the domain, HTTPS URL, and support
  email. The TS files also export the `LEGAL` object from `[legal]`.
- The same generator emits `frontend/src/shared/styles/tokens.css`,
  `mobile/src/shared/ui/tokens.ts`, the marked title/meta block in
  `frontend/index.html`, and `expo.name` plus the splash-screen background
  color in `mobile/app.json`. Never edit generated artifacts by hand;
  `python3 scripts/gen_brand.py --check` verifies they match the toml.
- Frontend consumers import generated identity constants; `BrandMark.tsx`
  displays the shared name. Use `python3 scripts/rebrand.py` when also
  applying deployment settings (see §6.2); it runs the generator afterwards.

### 1.2 Backend app name
- When `[brand].name` differs from `SaaS Template`, rebrand.py replaces that
  name in the env examples (`APP_NAME` and placeholder `EMAIL_FROM_NAME`).
  Empty or custom sender names stay unchanged. Real `.env` / `env/<slug>.env`
  files on your machines still need populating or updating yourself.
- `backend/app/core/config.py` — `app_name` defaults to `BRAND_NAME` from the
  generated `brand.py` (override per deployment with `APP_NAME` in env). Feeds
  the FastAPI docs title, email copy, and the **fallback email sender display
  name** (`email_sender` property).
- `backend/app/core/email/layout.py` — the email footer renders
  `© {app_name}`; the CTA button and heading colors come from `[theme.colors]`, and
  email neutrals from `[theme.email]` in `shared/brand.toml`.

### 1.3 Browser tab / SEO / brand assets
- `frontend/index.html` — the `<title>`, `meta description`, theme-color, and
  Open Graph tags between the `<!-- gen:brand -->` markers are generated from
  `shared/brand.toml`; edit the toml, not the block.
- `frontend/public/favicon.svg` is a neutral placeholder mark — replace it
  with your brand's. Add an `apple-touch-icon.png` and `og-image.png` to
  `frontend/public/` and link them in `index.html`:
  ```html
  <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
  <meta property="og:image" content="https://<your-domain>/og-image.png" />
  <meta property="og:url" content="https://<your-domain>" />
  ```
- Optionally add a `frontend/public/llms.txt` describing your product for LLM
  crawlers (the API docs page links `/docs/api.md` for this purpose too).

### 1.4 Package names (optional, cosmetic)
- `frontend/package.json` — `"name"`.
- `backend/pyproject.toml` — project name/description.

---

## 2. Frontend pages & copy

Routes are wired in `frontend/src/App.tsx`; paths live in
`frontend/src/shared/lib/routes.ts`. Use `ROUTES` for links, navigation, and
URL builders, and `ROUTE_PATTERNS` for parameterized route declarations. Add
paths there instead of hardcoding them in components. Pages live as vertical
slices under `frontend/src/features/`.

### Public routes
| Route | Component | Customize |
|-------|-----------|-----------|
| `/` | `features/home/HomePage.tsx` | **Hero, features, steps, FAQ, CTAs** — `HOME_CONTENT` in `frontend/src/shared/content/marketing.ts` |
| `/pricing` | `features/billing/components/PricingPage.tsx` | Heading + plan blurbs |
| `/docs` | `features/api-docs/` | Renders `frontend/public/docs/api.md` — see §7 |
| `/login`, `/register`, … | `features/auth/components/` | Standard auth pages — adjust copy if needed |
| `/terms`, `/privacy` | `features/legal/` | See §4 |
| `/privacy/request` | `features/legal/PrivacyRequestPage.tsx` | DSAR intake form (generic) |

All auth pages share `AuthSplitLayout.tsx`; its panel copy comes from
`AUTH_PANEL_CONTENT` in `frontend/src/shared/content/marketing.ts`. Update
the headline, blurb, access rows, status, and capabilities there.

### Authenticated routes (inside `AppLayout`, sidebar nav)
`/dashboard`, `/members`, `/billing`, `/settings`, `/api-keys`, `/profile`,
plus `/orgs/new` and `/invitations/accept`. The dashboard's stat strip and
recent-activity table run on the credit ledger — they work for any product
built on the credit engine. Sidebar items are `navItems` in
`components/AppLayout.tsx`.

### Admin routes
`/admin/*` (gated by `is_superuser`) under `features/admin/`. Internal
tooling — no branding needed. The Generations page exists because the
template ships AI generation slices; remove it if you drop those.

---

## 3. Theme & styling

Tailwind CSS v4 via the Vite plugin; palette and font-family tokens come
from `shared/brand.toml`, generated into `frontend/src/shared/styles/tokens.css`.
`frontend/src/index.css` imports that file and keeps base styles and animations;
it no longer defines the palette. `DESIGN.md` records the aesthetic direction.

- `[theme.colors]`: `ink`, `ink_soft`, `slate`, `mist`, `paper`, `line`,
  `teal`, `teal_deep`, `teal_glow`, `success`, `danger`, `info`, plus the
  marketing-surface keys `canvas`, `sand`, `sand_line`, `carbon`,
  `carbon_soft`, `lime`, `lime_deep`. The older key names are roles, not
  hues: `ink` is the text color, `teal*` is the signal color (links, focus,
  active state). CSS names replace underscores with hyphens; mobile semantic colors map to `match`,
  `nomatch`, and `review` in `mobile/src/shared/ui/tokens.ts`.
- `[theme.fonts]`: `display`, `body`, `mono`, `marketing` family names,
  emitted as `--font-display`, `--font-body`, `--font-mono`,
  `--font-marketing` with fallback stacks.
- `[theme.email]`: `background`, `surface`, `text`, `muted`, `faint`, `rule`,
  `on_accent` for inline email styles. Email headings use `ink`, CTAs use
  `teal_deep`; browser theme-color uses `ink`, mobile splash uses `teal_deep`.

To retheme: edit these tables, run `python3 scripts/gen_brand.py`, and record
visual decisions in `DESIGN.md`. Components consume tokens (`bg-[var(--ink)]`
etc.); keep palette hexes, palette rgba values, and raw Tailwind palette
classes out of components.

Fonts still need **both** the `[theme.fonts]` family names and matching
`@fontsource` imports in `frontend/src/main.tsx`. Install the corresponding
font packages in the frontend and update the imported weights manually
(currently Inter Variable / IBM Plex Mono); generation does not install
or load font assets. The placeholder icons (`frontend/public/favicon.svg`, `mobile/assets/images/*`,
and the iOS icon bundle `mobile/assets/expo.icon/`) and
`expo.android.adaptiveIcon.backgroundColor` in `mobile/app.json` are also
manual — the generated splash color does not update the adaptive icon.

---

## 4. Legal documents

`frontend/src/features/legal/TERMS_OF_SERVICE.md` and
`frontend/src/features/legal/PRIVACY_POLICY.md` retain `{{placeholders}}`.
`frontend/src/features/legal/LegalPage.tsx` strips HTML comments and fills
them at render time using `frontend/src/features/legal/model/placeholders.ts`
and the generated brand constants. Configure identity in `shared/brand.toml`
and regenerate; leave the placeholders in the document bodies.

| Placeholder | Source in `shared/brand.toml` |
|-------------|-------------------------------|
| `{{company_name}}` | `[legal].company_name` |
| `{{service_name}}` | `[brand].name` |
| `{{website_url}}` | `https://` + `[deploy].domain` |
| `{{support_email}}` | `[brand].support_email` |
| `{{effective_date}}` | `[legal].effective_date` |
| `{{jurisdiction_state}}` | `[legal].jurisdiction_state` |
| `{{jurisdiction_country}}` | `[legal].jurisdiction_country` |
| `{{arbitration_venue}}` | `[legal].arbitration_venue` |
| `{{minimum_age}}` | `[legal].minimum_age` (positive integer) |

The six `[legal]` keys above are separate from `[brand].legal_name`, which
supplies the general brand legal line. Unknown placeholders remain visible,
so review the rendered pages too. Both documents are generic SaaS starting
points (accounts, billing/credits, AI-output disclaimer, DSAR rights pointing
at `/privacy/request`) — **have counsel review them before launch.**

---

## 5. Errors (shared catalog)

`shared/errors.toml` is the **single source of truth** for every error code
and its user-facing message. It generates three artifacts via
`scripts/gen_errors.py`:
- `backend/app/core/error_codes.py`
- `frontend/src/shared/api/errorCatalog.ts`
- `docs/errors.md`

**Do not edit the generated files by hand.** To change wording or add a code:
```bash
# edit shared/errors.toml, then:
python3 scripts/gen_errors.py
python3 scripts/gen_errors.py --check   # CI drift gate
```

---

## 5b. Security & tenancy policy

These knobs are the **product security adaptation surface** — flip them per
project instead of forking auth/org use cases. Defaults are safe for a new
B2B SaaS clone.

| Env / setting | Default | Meaning |
|---------------|---------|---------|
| `DOMAIN_CLAIM_MODE` | `verified_claim` | `off` = never claim domains; `manual_only` = only via Settings → domain; `verified_claim` = auto-claim on org create **only after** email verification |
| `EMAIL_VERIFICATION_GATE` | `sensitive` | `none` = no gate; `sensitive` = org create, domain claim, invites, API keys, billing checkout/portal, LLM/generations require verified email; `login` = block sign-in until verified |
| `SIGNUP_ENUMERATION_PROTECTION` | `false` | Verify-first signup. `false` = register answers 409 for a taken email and the client signs the new user in at once (leaks account existence, bounded by the register rate limit). `true` = register always answers 202 "check your email" (an existing owner gets a notice email), and sign-in treats an unconfirmed account like a wrong password until the emailed link is used. Web and mobile switch flows from the response; the client `user_signed_up` event is not fired in this mode |
| Password min length | `12` | `[password].min_length` in `shared/policy.toml` + `python3 scripts/gen_policy.py` — backend check and frontend live feedback both consume the generated constant |

Request limits per client IP live in `[rate_limits]` in `shared/policy.toml`
(auth, community messaging, generations, LLM completion, privacy requests).
Use positive-count strings such as `5/minute` or `10/hour`; supported units
are `second`, `minute`, `hour`, and `day`. Run `python3 scripts/gen_policy.py`
to emit backend-only `RATE_LIMIT_*` constants in `backend/app/core/policy.py`.
Import those constants in limit decorators instead of hardcoding rates.

**Always on (not knobs):** Argon2 hashing, rotating HttpOnly refresh cookies,
tenancy 404-masking, API keys capped at MEMBER, Stripe/Resend webhook signature
verification, production boot guards for `SECRET_KEY` / Stripe webhook /
`RESEND_WEBHOOK_SECRET` (when `EMAIL_PROVIDER=resend`).

Composition root: sensitive routes take `CurrentVerifiedUser` from
`auth.interface.deps` (no-op when the gate is `none`).

---

## 6. Environment & deploy config

### 6.1 Dev — `.env.example`
rebrand.py sets `APP_NAME` from `[brand].name` in this example and replaces
any placeholder `EMAIL_FROM_NAME` (the dev example leaves it empty). Copy
the updated example to `.env`, or update your existing local file, and set:
- `SECRET_KEY=` (any long random string for dev)
- `EMAIL_*` — dev uses Mailpit by default (`EMAIL_PROVIDER=smtp`)
- `STRIPE_*`, `GEMINI_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`,
  `RESEND_*`, `SENTRY_DSN` — only the providers you actually use.

### 6.2 Prod — the shared platform + per-app project

Set `[deploy]` in `shared/brand.toml`: `slug` (replaces `myapp`), `domain`
(bare domain, replacing `your-domain.com`), `ghcr_org` (replaces `your-org`),
and `port_base` (first of five dev ports, default `21427`). Then run:

```bash
python3 scripts/rebrand.py --dry-run
python3 scripts/rebrand.py
```

Flags are optional overrides, written back to the toml, for example:
`python3 scripts/rebrand.py --slug acme --domain acme.com --ghcr-org acme-inc --name Acme --port-base 22000`.
`--name` sets `[brand].name`; other identity/legal fields still need editing.
Settings left at their placeholder values are skipped independently.
The script renames slug-named files via git-mv, rewrites references including
GHCR image owners and the brand name, runs `gen_brand.py` afterwards, and
sweeps for stragglers.
`--dry-run` writes nothing; `--no-gen` explicitly skips regeneration.
The list below describes the automatic rewrites, not extra manual steps.

Production runs as a **shared base + per-app compose project** pair on a
shared droplet (`/opt/prd-shared`):
- `docker-compose.prod.yml` — **shared platform infrastructure** (compose
  project `prd-shared`: Caddy reverse proxy + the `prd-shared-backend`
  network). One per droplet, shared by all apps — do **NOT** rename it per
  app; it contains no app slug.
- `docker-compose.myapp.yml` — this app's compose project (`name: myapp`,
  services `myapp-backend`, `myapp-frontend`, `myapp-worker`,
  `myapp-worker-heavy`, `myapp-beat`, volume `myapp_media`, image repo
  `ghcr.io/your-org/myapp/...`). Rename the file, the project name, and every
  `myapp` service/volume/image reference to your slug.
- `caddy.d/myapp.caddy` — the vhost (`your-domain.com` → your domain,
  upstream service names → your slug). Rename the file too.
- `env/myapp.env.example` — production env template (`APP_NAME`, managed
  DB/Valkey URLs + `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` per NAMING.md,
  Resend, Stripe, AI keys). The script sets the placeholder `APP_NAME` and
  `EMAIL_FROM_NAME` from `[brand].name`; populate the real droplet copy at
  `env/<slug>.env` yourself.
- `.env.prod.example` — shared platform config (Redis DB index registry —
  update the `myapp:` line). `.env.myapp-deploy.example` — the `APP_SHA`
  image pin; the script renames the example to `.env.<slug>-deploy.example`.
  Populate `.env.<slug>-deploy` on the droplet.
- `deploy.sh` + `scripts/rollout.sh` — zero-downtime rolling replace; update
  the `myapp-*` service names in deploy.sh and the compose/env file names in
  both.
- `.github/workflows/deploy-myapp.yml` — CI: build → test → push → deploy →
  health-gate (`https://your-domain.com/api/health`) → stable-tag. Rename the
  file, the concurrency groups, `IMAGE_PREFIX`, and the `myapp` service names.
- `.github/workflows/cleanup-buildcache.yml` — GHCR cache pruning; update the
  `myapp/${{ matrix.package }}` package name.
- `setup-platform.sh` — first-time droplet bootstrap (network, tree, secret
  placeholders); update the `APPS=(myapp)` list.
- `docker-compose.yml` (dev) — `name: myapp` project name (cosmetic but keeps
  local container/volume names on-slug).
- `docs/backups.md` — the media-volume snapshot example uses the
  `myapp_myapp_media` volume name (project + volume key); it follows your
  slug.
- `.env.example`, `frontend/public/docs/api.md`, `backend/pyproject.toml`,
  and `README.md` — replace `SaaS Template` when `[brand].name` is no longer
  that placeholder: the dev `APP_NAME`, API docs title, backend description,
  and README identity follow automatically. The API docs domain follows
  `[deploy].domain` too.
- `docs/monitoring.md` — rewrite slug/domain in health-check URLs, resource
  names, and deploy-state paths.
- `frontend/nginx.conf` — rewrite the slug in the Caddy vhost comment.
- `scripts/check_env_examples.py` — rewrite the production env-example path
  to follow the renamed file.

### 6.3 Google Analytics
Fully env-driven: set the `VITE_GA_MEASUREMENT_ID` build arg (CI repo
variable → `frontend/Dockerfile.prod`). Unset = GA and the consent banner's
analytics category stay inert. No code changes.

GA is one of two analytics sinks. The other — the first-party
`activity_events` table — needs no configuration and works with GA unset.
Event taxonomy, the consent/opt-out model, and what to change when you swap
the flagship feature (the activation event) are in
[docs/analytics.md](analytics.md). Rebranding touches one thing there: the
"24 months" retention figure in the privacy policy must match
`[analytics].activity_event_retention_days` in `shared/policy.toml`.

---

## 7. Public API docs

`frontend/public/docs/api.md` is the canonical API reference — fetched at
runtime by the `/docs` page and downloadable for LLM agents (`docs/api.md` is
just a stub pointing at it). `scripts/rebrand.py` rewrites its
`your-domain.com` domain from `[deploy].domain`; document your product's endpoints as you add slices (the template documents
credits, LLM completions, and generations).

---

## 8. DigitalOcean resource naming (reference)

`NAMING.md` defines the `[env]-[app]-[service]` convention (e.g.
`prd-myapp-app`, `prd-myapp-db`, `prd-myapp-cache`) and image repos as
`<app>/backend`, `<app>/frontend`. Use your slug as `<app>` consistently when
provisioning.

---

## 9. Final checklist

- [ ] `[brand]`, `[deploy]`, `[legal]`, and `[theme.*]` in `shared/brand.toml` filled in
- [ ] `python3 scripts/rebrand.py` run (brand artifacts regenerated, sweep reviewed)
- [ ] Automatic `APP_NAME` / placeholder `EMAIL_FROM_NAME` rewrites in env examples verified; real `.env` / `env/<slug>.env` files populated or updated
- [ ] Favicon swapped, og-image added, Android adaptive-icon color reviewed
- [ ] `HOME_CONTENT` + `AUTH_PANEL_CONTENT` in `frontend/src/shared/content/marketing.ts` rewritten
- [ ] `[theme.colors]`, `[theme.fonts]`, `[theme.email]` + `DESIGN.md` reviewed; font packages/imports updated if changing fonts
- [ ] Policy knobs including `[rate_limits]` reviewed (`shared/policy.toml` + `python3 scripts/gen_policy.py`)
- [ ] Both legal pages render the nine placeholders correctly + counsel review
- [ ] Security policy knobs reviewed (`DOMAIN_CLAIM_MODE`, `EMAIL_VERIFICATION_GATE`, `SIGNUP_ENUMERATION_PROTECTION`)
- [ ] `.env` / `env/<slug>.env` populated (secrets, provider keys, Resend webhook secret in prod) — `python3 scripts/check_env_examples.py` passes
- [ ] Stripe products/prices created: `docker compose exec backend python scripts/stripe_sync.py`, env lines pasted, `--check` passes
- [ ] `frontend/public/docs/api.md` updated for your endpoints; domain rewrite verified
- [ ] New frontend paths registered in `frontend/src/shared/lib/routes.ts`
- [ ] §0 sanity-sweep grep reviewed; no unintended template identity remains
- [ ] `docker compose up --build` boots and the rebrand renders

## Storage, plans, and entitlements

- Storage provider settings live in `backend/app/core/config.py`; configure
  `STORAGE_PROVIDER` and the bucket settings in [provisioning.md](provisioning.md).
  Extend `backend/app/domains/files/domain/policy.py` for upload purposes;
  only user-owned avatars ship today (PNG, JPEG, WebP). Size, quota, signed-URL
  lifetime, and pending cleanup policy live in `[uploads]` in
  `shared/policy.toml`; regenerate with `python3 scripts/gen_policy.py`.
- Edit `PLANS` in `backend/app/domains/billing/domain/value_objects.py` for
  prices and paid monthly credits. Free's null allowance uses the credits
  slice's `MONTHLY_ALLOWANCE_CREDITS` fallback. Run
  `python backend/scripts/stripe_sync.py` with backend settings loaded, apply
  its printed env lines, then run it with `--check`. Missing price ids disable
  the corresponding checkout interval. Community membership uses its separate
  user-level catalog in `backend/app/domains/community/domain/value_objects.py`.
- `[billing].plan_grace_days` is 3; `[billing].trial_days` is 0 (disabled).
  If changing either, regenerate policy and update the Terms in the same change.
  Plan changes and cancellation use the Stripe Customer Portal; configure its
  products/prices and period-end cancellation behavior for your offering.
- Edit `PLAN_ENTITLEMENTS` in
  `backend/app/domains/entitlements/domain/entities.py`: null is unlimited,
  zero excludes a feature, and a positive integer caps capacity. Shipped keys
  are `seats` and `api_keys`. Free limits are 5/5, Pro 15/20, Team unlimited/50.
  Unexpired superuser overrides take precedence and are audited; expiry or
  removal restores the plan default. Feature flags still govern global module
  availability. Use the entitlement service for capacity checks in the write
  transaction; client gates are presentation only.
