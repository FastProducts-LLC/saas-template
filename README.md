# SaaS Template

[![CI](https://github.com/FastProducts-LLC/saas-template/actions/workflows/ci.yml/badge.svg)](https://github.com/FastProducts-LLC/saas-template/actions/workflows/ci.yml)
[![CodeQL](https://github.com/FastProducts-LLC/saas-template/actions/workflows/codeql.yml/badge.svg)](https://github.com/FastProducts-LLC/saas-template/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A reusable, multi-tenant SaaS starter (see [docs/customization.md](docs/customization.md)
to rebrand it into your product):

- **Backend** — FastAPI + async SQLAlchemy 2.0 + Alembic (Postgres), structured as **DDD vertical slices by feature**
- **Frontend** — React 19 + TypeScript + Vite + Tailwind v4 + TanStack Query, mirrored feature-slice layout
- **Multi-tenancy** — shared schema with `organization_id` scoping; organizations with sub-users (owner / admin / member roles) and email invitations
- **Auth** — self-contained JWT: argon2 password hashing, 15-min access tokens, rotating refresh tokens in an httpOnly cookie
- **Billing** — Free, Pro, and Team **organization** plans plus one-time credit packs, Checkout + Customer Portal + Stripe-authoritative subscription webhooks
- **Storage** — local or S3-compatible object storage for generations and community avatar uploads
- **Entitlements** — plan seat/API-key limits, audited per-org admin overrides, and web/mobile usage displays
- **SaaS Essentials** - authenticated `/saas-features` catalog covering 28 reusable SaaS modules, marking what is included and what to build next

To rebrand, edit `shared/brand.toml` (identity, deployment, legal details,
palette, font families, email colors), then run `python3 scripts/rebrand.py`.
It applies deployment settings and regenerates brand constants and theme tokens,
including `frontend/src/shared/styles/tokens.css`. Rewrite landing/auth-panel
copy in `frontend/src/shared/content/marketing.ts`; fonts, icons, and legal
review still need manual work (see the customization guide).

> **Legal pages are templates, not legal advice.** The Terms of Service and
> Privacy Policy (`frontend/src/features/legal/*.md`, filled from `[legal]` in
> `shared/brand.toml`) are starting points with placeholder company details and
> an example Delaware jurisdiction. Have a lawyer review them for your product,
> jurisdiction, and data practices before you launch.

## Quickstart

```bash
cp .env.example .env        # set SECRET_KEY; Stripe keys optional at first
docker compose up --build
```

| Service     | URL                          |
|-------------|------------------------------|
| Frontend    | http://localhost:21427       |
| Backend API | http://localhost:21428/api   |
| API docs (product) | http://localhost:21427/docs — also `/docs/api.md` for LLMs |
| API docs (Swagger, local) | http://localhost:21428/api/docs |
| Postgres    | localhost:21429 (app/app)    |
| Valkey      | localhost:21430 (Redis-compatible) |
| Mailpit UI  | http://localhost:21431       |

Register an account, create an organization, invite a teammate (the invite
email lands in Mailpit), and you have a working multi-tenant app.

Or skip the signup flow entirely:

```bash
docker compose exec backend python scripts/seed_dev.py
```

seeds `dev@example.com` — an email-verified **superuser** owning "Dev Org"
with 500 credits — and prints its password. The password is generated once
per checkout (`backend/.dev-secrets/seed_password`, gitignored; override with
`SEED_DEV_PASSWORD`), never a shared constant: this repo is public and the dev
API is reachable from your LAN. Idempotent; refuses to run off a local dev
stack. The local `SECRET_KEY` is generated the same way, so the placeholder in
`.env` never signs a token.

## Architecture

Each feature is a **vertical slice** owning its full stack, structured as four
Clean Architecture layers (dependencies point inward: interface →
infrastructure → application → domain):

```
backend/app/
├── core/                      # shared kernel: config, db, security, errors, email, celery
├── domains/
│   ├── auth/
│   │   ├── domain/            # PURE Python: entities (@dataclass), errors, policies
│   │   │   ├── entities.py    #   User.register(), RefreshToken.revoke(), …
│   │   │   ├── errors.py      #   AppError subclasses with internal_codes
│   │   │   └── services.py    #   password policy (no I/O, unit-testable)
│   │   ├── application/
│   │   │   ├── ports.py       #   Protocols: UserRepository, PasswordHasher, AuthMailer…
│   │   │   └── use_cases.py   #   RegisterUser, LoginUser, ChangePassword, … (DI via ports)
│   │   ├── infrastructure/
│   │   │   ├── orm.py         #   Tables + imperative mapping onto the pure entities
│   │   │   ├── repositories.py#   SqlAlchemy* implementations of the ports
│   │   │   └── …adapters      #   mailer, marketing list, argon2/JWT services
│   │   └── interface/
│   │       ├── router.py      #   thin HTTP: parse → use case → serialize
│   │       ├── schemas.py     #   Pydantic request/response DTOs
│   │       └── deps.py        #   composition root + CurrentUser for other slices
│   ├── organizations/         # tenancy core: orgs, memberships, roles, invitations
│   ├── billing/               # Stripe behind a PaymentGateway port (anti-corruption)
│   ├── credits/               # org-level credit engine: reserve → capture/release
│   ├── generations/           # AI jobs (+ tasks.py / worker.py at slice root)
│   ├── emails/                # provider webhooks → consent sync
│   ├── blog/                  # blog CMS: superuser authoring + public reader (global, not org-scoped)
│   └── admin/                 # cross-tenant superuser views (owns admin_audit_log)
└── main.py                    # wires routers together

frontend/src/
├── shared/                    # api client, ui atoms, lib (never imports features)
├── components/                # AppLayout, RequireAuth
└── features/                  # mirrored slices: components/ api/ model/ index.ts

mobile/                        # Expo (React Native) app for iOS + Android
└── src/
    ├── app/                   # expo-router screens (sign-in, tabs, detail)
    ├── shared/api/            # native port of the web API client (SecureStore tokens)
    └── features/              # same endpoints/keys/hooks slice pattern (see mobile/README.md)
```

Domain entities are mapped to tables with SQLAlchemy **imperative mapping**
(`infrastructure/orm.py`), so repositories return change-tracked pure
entities — no ORM base classes in the domain, no mapper boilerplate. Use cases
receive their dependencies as `typing.Protocol` ports, so they unit-test with
in-memory fakes and no database.

### Multi-tenancy rules

1. Every tenant-scoped table carries `organization_id` (FK, `ON DELETE CASCADE`).
2. Endpoints under `/orgs/{org_id}/...` resolve access through
   `require_role(...)` in `domains/organizations/interface/deps.py` — it 404s
   for non-members (never leaking org existence) and 403s for insufficient roles.
3. Repositories always filter by `organization_id`. Never trust an id from the
   client without going through a membership check.

### Adding a feature slice (e.g. `projects`)

1. `app/domains/projects/` with the four layers: `domain/entities.py`
   (include `organization_id`!) + `domain/errors.py`, `application/ports.py` +
   `application/use_cases.py`, `infrastructure/orm.py` +
   `infrastructure/repositories.py`, `interface/{router,schemas,deps}.py`.
2. Scope endpoints with `CurrentMember` / `CurrentAdmin` from
   `app.domains.organizations.interface.deps`.
3. Register `app.domains.projects.infrastructure.orm` in `alembic/env.py`, then:
   `docker compose exec backend alembic revision --autogenerate -m "add projects"`
   and `docker compose exec backend alembic upgrade head`.
4. Include the router in `app/main.py`.
5. Mirror it in `frontend/src/features/projects/` (an `api.ts` + pages) and add
   routes in `App.tsx`.

## Error handling

Every error in the system is defined once in **`shared/errors.toml`** — UX
copy, HTTP status, severity, frontend display routing (`field`/`toast`/
`banner`/`page`), and auto-retry policy. `python3 scripts/gen_errors.py`
generates the backend code table, the frontend catalog, and `docs/errors.md`
(the support lookup table); CI and contract tests fail on drift.

- **Wire format** — RFC 9457 `application/problem+json`:
  `{type, title, status, code, instance, detail, fields?}`. `instance` is the
  request's correlation id (also the `X-Request-ID` header); `fields` carries
  per-input validation messages for form binding.
- **Backend** — slices raise `AppError` subclasses carrying an
  `internal_code`; handlers in `app/core/error_handling.py` render the
  envelope, emit one structured JSON log line per error (greppable/alertable
  per code), and stash full request context in Redis for 7 days. Unhandled
  exceptions become `ERR_SRV_001` — tracebacks never cross the wire.
- **Frontend** — `shared/api` normalizes every failure into a catalog-aware
  `ApiError` (`userMessage`, `actionStep`, `reference`, `fields`). Toasts,
  the offline banner, and the maintenance takeover are global
  (`lib/errors.tsx`); forms render `field`-routed errors inline. Every error
  surface shows `code · ref` with a "Copy details" button.
- **Safe retries** — mutating requests carry an `Idempotency-Key` reused
  across retries; the backend replays the original response on duplicates, so
  a retried timed-out checkout can't double-charge.
- **Support loop** — a user reports `ERR_BILL_002 · e7f3a2b1`; a superuser
  resolves it with `GET /api/admin/errors/e7f3a2b1` (route, status, client,
  traceback for 500s).

Codes are permanent: never reuse or renumber — mark dead ones
`deprecated = true` in the catalog instead.

## Stripe setup

1. Set `STRIPE_SECRET_KEY`, then run `python backend/scripts/stripe_sync.py`
   in the configured backend environment. It syncs credit packs, community
   memberships, and org plans; paste its printed price env lines into your
   environment. `python backend/scripts/stripe_sync.py --check` verifies
   configured prices; unset plan intervals remain unavailable for checkout.
2. Forward webhooks locally:
   ```bash
   stripe listen --forward-to localhost:21428/api/billing/webhook
   ```
   Set the printed signing secret as `STRIPE_WEBHOOK_SECRET`.
3. Configure the Stripe Customer Portal for plan changes and period-end
   cancellation. The web Billing page starts plan checkout and opens the
   portal for existing subscriptions; credit packs remain available on any plan.

`backend/app/domains/billing/domain/value_objects.py` owns the plan catalog.
Org subscriptions share the org billing customer; community premium remains
an independent user-level subscription. Checkout completion and subscription
created/updated/deleted events trigger a fresh Stripe subscription read,
including a second read under the org lock. Paid access survives `past_due`
for 3 days past the paid-through date; trials are disabled by default in
`[billing]` in `shared/policy.toml`. See [runbook.md](docs/runbook.md) for
webhook recovery and revenue reconciliation.

## Storage and plan limits

`app.core.storage` selects local disk (`STORAGE_PROVIDER=local`, `MEDIA_DIR`)
or S3-compatible storage (`STORAGE_PROVIDER=s3`). Generations use the same
port; the authenticated file download still returns bytes, and the separate
file-URL endpoint supplies a temporary S3 URL (`url: null` under local storage;
use the file download).
Community avatars use the files slice's upload slot → PUT → confirmation
flow; confirmation checks size and image signature. Profile images are public
by unguessable link. See [provisioning.md](docs/provisioning.md) for bucket
credentials and browser-upload CORS, and [runbook.md](docs/runbook.md) before
moving existing media.

`backend/app/domains/entitlements/domain/entities.py` defines seat and active
API-key limits. Seats include members and unexpired pending invitations.
Superusers can set audited, optionally expiring org overrides. Server-side
checks enforce capacity; web and mobile show usage and limits. Global feature
flags remain separate module switches. See [customization.md](docs/customization.md)
for the catalog and policy adaptation points.

## Credits & AI generations

Metered AI usage runs through an org-level **credit engine** (`domains/credits`)
with an auth/capture lifecycle, so users are only charged for delivered results:

1. **Reserve** — credits are held (deducted from the available balance) when a
   job is accepted; insufficient credits fail the request up front.
2. **Capture** — the hold is finalized when the result is delivered.
3. **Release** — failures refund the hold; abandoned holds expire on a per-action
   TTL and refund automatically — swept lazily on wallet access, plus a Celery
   beat task (`credits/tasks.py`) every 10 minutes so dormant orgs get their
   refunds too.

Every movement is an append-only row in `credit_transactions` (the ledger sums
to the wallet balance), surfaced on the **Billing** page with per-member
attribution. The effective plan supplies the monthly allowance: Pro grants
200 credits and Team 1000; Free uses `MONTHLY_ALLOWANCE_CREDITS` (default 0).
Grants happen on first wallet touch each calendar month, including annual
subscriptions, and unused credits carry over. Upgrades top up the allowance
difference idempotently. Action costs, TTLs, and the pack catalog live in
`domains/credits/domain/value_objects.py`.

The `generations` and `llm` slices are **backend reference implementations**
of this reserve/settle pattern against real providers — Gemini **nano-banana**
images, OpenAI **gpt-image-1** images, **VEO 3.1** video, and text
completions. There is no user-facing Generate page; the only UI is an admin
monitor (`/admin/generations`). `POST /orgs/{id}/generations` reserves credits
and queues a Celery job on the `heavy` queue; the worker calls the provider
(no DB transaction held), stores the asset through the configured storage
provider, then captures or releases the hold atomically with the job status. Set `GEMINI_API_KEY` /
`OPENAI_API_KEY` in `.env` to enable providers; an unset key fails fast
(`ERR_GEN_002`) before any credits are held. When building your product's
metered features, copy these slices' shape: the `hold_credits` context manager
from `app.domains.credits.application.facade` for in-request flows, or the
generations-style reserve-in-request / settle-in-worker split for jobs.

## Auth model

- Access token: JWT (HS256), 15 minutes, held in frontend memory only.
- Refresh token: opaque, sha256-hashed at rest, 30 days, rotated on every use,
  delivered as an httpOnly `SameSite=Lax` cookie scoped to `/api/auth`.
- The Vite dev server proxies `/api` to the backend so the app and API share an
  origin and cookies need no cross-site configuration.
- Native clients (`X-Client: mobile` header) get the refresh token in the
  response body instead of the cookie and send it back in the request body on
  refresh/logout — React Native has no httpOnly cookie jar. The mobile app
  stores it in the iOS Keychain / Android Keystore (`expo-secure-store`).
- Email-link flows (account activation, password reset) use short-lived,
  purpose-scoped JWTs. Reset links are single-use — the token embeds a
  fingerprint of the current password hash — and a successful reset revokes
  every refresh token.

## Email (transactional + marketing)

Email goes through a pluggable provider behind `app/core/email/`
(`EMAIL_PROVIDER` env var):

- **`smtp`** (default) — plain SMTP, pointed at Mailpit in dev. Transactional
  only; marketing-list calls are logged no-ops.
- **`resend`** — [Resend](https://resend.com) API: transactional sends plus
  marketing contacts/segments. Set `RESEND_API_KEY`, create a "Marketing"
  segment and set `RESEND_SEGMENT_MARKETING`, and (optionally) point a webhook
  at `/api/webhooks/resend` with `RESEND_WEBHOOK_SECRET` for unsubscribe/bounce
  sync.

To add SendGrid/SES/Postmark, implement `EmailProvider`
(`app/core/email/base.py`) in a new module and register it in the factory in
`app/core/email/__init__.py`.

**Transactional** (no opt-in needed; all sends are best-effort and never fail
the request): welcome + activation on signup, re-sendable verification,
password reset, a "your password was changed" security notice (after a change
or a reset), org invitations, credit-pack receipts, low-balance alerts.

**Suppression**: a hard bounce or spam complaint (Resend webhook) flags the
user `email_suppressed`. The flag is enforced inside `send_email_task` — the
one chokepoint every mailer goes through — so suppressed addresses get no mail
of any kind, whichever slice asked for the send.

**Marketing** (GDPR consent): users enter the marketing list only with
`marketing_opt_in=True` — captured at signup or via `PATCH /auth/me`. Opting
out marks the contact unsubscribed at the provider; an inbox-level unsubscribe
flows back through the webhook and flips `marketing_opt_in` off, so consent
state stays in sync in both directions. Account deletion should call
`delete_marketing_contact` (GDPR erasure).

Broadcasts themselves are composed/sent from the provider dashboard (e.g.
Resend Broadcasts targeting the Marketing segment) — application code only
manages who's in the segment.

## Production deploy (optional; one Docker host, zero downtime)

Deploying is optional, and this is one documented path, not a requirement. It
needs a single Linux host with Docker (the docs use a DigitalOcean droplet,
but any VPS works), plus a managed or self-run Postgres and Valkey. The
layout is called "shared" because one Caddy can front several apps on the
same host later; with one app it is simply Caddy + this app:

```bash
# on the host (full steps, env files and DNS: docs/provisioning.md)
./setup-platform.sh                                   # network + /opt/prd-shared tree
cd /opt/prd-shared
docker compose -f docker-compose.prod.yml up -d caddy # Caddy: 80/443, auto-HTTPS
./deploy.sh stable                                    # or <git-sha>; pulls from GHCR
```

`deploy.sh` pulls the images CI pushed to GHCR (`ghcr.io/<ghcr_org>/<slug>/…`),
so build and push them first, either with the workflow or by hand.

The GitHub Actions deploy workflow is **off by default**: every job is skipped
until you set the repository variable `DEPLOY_ENABLED=true` and the
`DROPLET_HOST` / `DROPLET_USER` / `DROPLET_SSH_KEY` secrets. Tests for pull
requests run separately in [ci.yml](.github/workflows/ci.yml). Prefer another
platform (Fly, Render, Kubernetes…)? Reuse `backend/Dockerfile`,
`frontend/Dockerfile.prod`, and `docker-compose.myapp.yml` as the reference
for which processes to run (api, worker, worker-heavy, single beat).

CI ([deploy-myapp.yml](.github/workflows/deploy-myapp.yml)) tests, builds and
pushes the backend image and the static frontend bundle
(`frontend/Dockerfile.prod`, served by nginx) to GHCR, then deploys to the
shared droplet over SSH. Production is a **base + per-app** pair in
`/opt/prd-shared`: `docker-compose.prod.yml` (compose project `prd-shared`,
Caddy only — shared by every app on the droplet) plus
`docker-compose.myapp.yml` (this app's own compose project). Manual deploys
run the same mechanism on the droplet:

```bash
cd /opt/prd-shared
./deploy.sh <git-sha>            # or no argument for the :stable tag
```

The rollout pulls images, runs migrations against the new image, then does a
**scale-based rolling replace** per service via `scripts/rollout.sh`: docker
compose silently ignores `deploy.update_config` / `order: start-first`
(Swarm-only keys — a plain `up -d` is stop-first with ~35s downtime), so the
script instead scales to N+1 replicas, waits for the new replica's healthcheck
(`/api/health` verifies the DB), then drains the old one. Caddy is the sole
public entrypoint (80/443, automatic HTTPS); its `dynamic a` upstreams
re-resolve Docker DNS every 3s and passively route around containers during
the swap. A failed rollout leaves the old replica serving; CI additionally
auto-rolls-back to the last-good SHA and only promotes images to `:stable`
after the public health gate passes. Once the `DROPLET_*` secrets are set, the
CI `deploy` job runs on every push to `main`. See
[docs/runbook.md](docs/runbook.md) for the full mechanics.

**Migrations must be expand/contract** — they run against the new image while
the old code is still serving (add columns now, drop them a release later).

### Operations

- [docs/runbook.md](docs/runbook.md) — day-2 ops: deploys, rollback
  (`./deploy.sh --rollback`), health-gate debugging, Celery ops, common failures.
- [docs/provisioning.md](docs/provisioning.md) — first-time DigitalOcean setup:
  droplet, managed Postgres/Valkey, `.env.prod`, DNS, GitHub Actions secrets.
- [docs/backups.md](docs/backups.md) — managed-DB backups + PITR, restore drill,
  and the `media` volume / Valkey durability story.
- [docs/analytics.md](docs/analytics.md) — product analytics: the first-party
  `activity_events` table + consent-gated GA4 behind one `track()` facade,
  event registry, opt-out model, coverage matrix, DAU/funnel queries
- [docs/monitoring.md](docs/monitoring.md) — uptime checks, resource alerts,
  and the incident-response process (severities, postmortem template).
- [docs/customization.md](docs/customization.md) — rebranding checklist: every
  identity touchpoint to change when turning the template into your product.

## Notes for production

- On DigitalOcean, name resources per [NAMING.md](NAMING.md) — `[env]-[app]-[service]`,
  e.g. `prd-<app>-db`, `prd-<app>-cache`.
- Postgres and Valkey are **not** in the production compose files — point
  `DATABASE_URL` / `REDIS_URL` (and `CELERY_BROKER_URL` /
  `CELERY_RESULT_BACKEND`) at the managed cluster/Valkey (stateful services
  shouldn't do rolling container swaps).
- Set `ENVIRONMENT=production` (enables `Secure` cookies), a strong `SECRET_KEY`,
  `EMAIL_PROVIDER=resend` + `RESEND_API_KEY` (or real SMTP credentials), and
  live Stripe keys + a dashboard-configured webhook endpoint.
- Valkey serves double duty: rate limiting on auth endpoints and the Celery
  broker/result backend. The worker and beat services reuse the backend
  image (no extra CI build); scale the default-queue workers with
  `docker compose -f docker-compose.myapp.yml --env-file .env.myapp-deploy up -d --no-deps --no-recreate --scale myapp-worker=3 myapp-worker`,
  but never scale `myapp-beat` past one instance.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the
dev setup, conventions, and checks CI runs. Please report security issues
privately as described in [SECURITY.md](SECURITY.md), not in public issues.

## License

[MIT](LICENSE) © Fast Products, LLC
