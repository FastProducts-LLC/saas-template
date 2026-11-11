# Conventions

The working rules for this codebase: everyday commands and the conventions
every change follows. See [README.md](../README.md) for the full architecture
and [customization.md](customization.md) for the rebranding checklist.

## Commands

- `docker compose up --build` — run everything (frontend :21427, API :21428, Postgres :21429, Valkey :21430, Mailpit :21431, plus Celery `worker` (default queue) + `worker-heavy` (heavy queue) + `beat`)
- `docker compose exec backend alembic revision --autogenerate -m "msg"` — new migration (run migrations only inside Docker)
- `docker compose exec backend alembic upgrade head` — apply migrations
- `docker compose exec worker celery -A app.core.celery_app call app.ping` — smoke-test the task queue
- `docker compose exec worker celery -A app.core.celery_app inspect active` — what workers are running right now
- `docker compose exec backend python scripts/seed_dev.py` — seed a dev superuser (`dev@example.com`; password is generated per checkout, printed by the script and kept in `backend/.dev-secrets/seed_password` — demo members have no known password, impersonate them) with an org, 500 credits, the community flag on, demo community members (one premium, no Stripe needed), and a seeded DM (idempotent, dev-only)
- `docker compose exec backend pytest` — run the backend test suite (incl. error-catalog contract tests; if pytest is missing in the dev image, `pip install -r requirements-dev.txt` inside the container first)
- `cd frontend && npm test` — run the frontend test suite (vitest + testing-library)
- `cd mobile && npm start` — Expo dev server for the iOS/Android app (`npm run typecheck` / `npm test` for checks; backend URL is auto-derived from the Metro host, see mobile/README.md)
- `python3 scripts/gen_errors.py` — regenerate error-code artifacts after editing `shared/errors.toml` (`--check` for CI)
- `python3 scripts/gen_policy.py` — regenerate cross-stack policy constants and backend-only rate limits after editing `shared/policy.toml` (`--check` for CI)
- `python3 scripts/gen_enums.py` — regenerate the frontend/mobile TS unions from the backend domain enums after adding/renaming an enum member (`--check` for CI)
- `python3 scripts/gen_events.py` — regenerate the product-analytics event registry (`frontend/src/shared/lib/events.ts`, `backend/app/domains/analytics/domain/events.py`) after editing `shared/events.toml` (`--check` for CI)
- `python3 scripts/gen_brand.py` — regenerate identity constants, tokens.css/mobile tokens, index.html title/meta, and mobile name/splash color after editing `shared/brand.toml` (`--check` for CI)
- `python3 scripts/check_env_examples.py` — verify every Settings field is documented in an `.env` example (runs in CI)
- `python3 scripts/rebrand.py` — read `[deploy]` from `shared/brand.toml`, rename/rewrite slug/domain/GHCR owner/ports, regenerate brand artifacts; optional flags override and update the toml (`--dry-run` previews)
- `docker compose exec backend python scripts/stripe_sync.py` — create/update Stripe Products+Prices from the credit-pack catalog AND the community membership and organization plans (recurring), printing the env lines (`--check` verifies displayed prices match what Stripe charges)
- `python backend/scripts/reconcile_revenue.py --json` — read-only local/Stripe subscription and catalog-MRR comparison (configured backend environment required)
- `python backend/scripts/migrate_media_to_storage.py --dry-run` — preview copying generation assets from `MEDIA_DIR` to S3; omit `--dry-run` to copy, preserving keys and local sources
- `./deploy.sh [sha]` — zero-downtime production deploy, run on the droplet
  from `/opt/prd-shared` (scale-based rolling replace via `scripts/rollout.sh`,
  gated on healthchecks — plain `up -d` would be stop-first; compose ignores
  Swarm-only `update_config`)
- API docs: http://localhost:21428/api/docs

## Conventions

- Never hardcode brand tokens/identity (`shared/brand.toml`), marketing copy (`frontend/src/shared/content/marketing.ts`), route paths (`frontend/src/shared/lib/routes.ts`), or rate limits (`[rate_limits]` in `shared/policy.toml`).
- One feature = one vertical slice in `backend/app/domains/<name>/` with four
  layers (Clean Architecture; dependencies point inward only):
  - `domain/` — pure-Python entities (`@dataclass`), value objects, domain
    errors, and policy functions. Zero framework/ORM imports.
  - `application/` — `use_cases.py` (one class per operation, constructor-
    injected ports), `ports.py` (`typing.Protocol` interfaces for everything
    the use cases need), plus `queries.py`/`dtos.py`/`facade.py` where useful.
  - `infrastructure/` — `orm.py` (SQLAlchemy `Table`s + **imperative mapping**
    onto the domain entities — repositories return change-tracked pure
    entities, no mapper boilerplate), `repositories.py`, and adapters
    (gateways, notifiers, mailers) implementing the ports.
  - `interface/` — `router.py` (thin: parse → use case → serialize),
    `schemas.py` (Pydantic at the HTTP edge only), `deps.py` (the composition
    root — the ONLY place use cases meet concrete adapters; also exports
    FastAPI deps like `CurrentUser` for other slices).
  - Slice root holds worker entry points when needed: `tasks.py` (Celery) and
    `worker.py` (background-job composition root) — see generations.
  Mirror the slice in `frontend/src/features/<name>/`.
- Unit-test use cases without a database: construct them directly with
  in-memory fakes of the ports (`docker compose exec backend pytest`).
- Frontend slice layout: `components/` (UI only), `api/` (`endpoints.ts`
  fetchers, `keys.ts` query-key factory, `hooks.ts` TanStack Query domain
  hooks that own cache invalidation), `model/` (types + pure logic +
  feature-owned context), `index.ts` (public API). Components never touch
  `queryClient`, endpoints, or `localStorage` directly — only domain hooks.
  Cross-feature imports go through the other feature's `index.ts` only.
  HTTP client + shared UI atoms live in `frontend/src/shared/{api,ui,lib}`
  (infrastructure — never imports from features).
- Mobile (`mobile/`, Expo + expo-router): same slice pattern under
  `mobile/src/features/`; screens live in `mobile/src/app/`. The API client
  (`mobile/src/shared/api/client.ts`) is a native port of the web client —
  requests send `X-Client: mobile`, so auth endpoints return the rotating
  refresh token in the body (stored in SecureStore) instead of the httpOnly
  cookie. Its `errorCatalog.ts` is generated by `scripts/gen_errors.py` too.
- Feature flags: runtime module toggles live in `domains/feature_flags`
  (`feature_flags` table; defaults + valid keys in `KNOWN_FLAGS` in its
  `domain/entities.py`). Superusers toggle at `/admin/flags` (no restart);
  clients bootstrap from unauthenticated `GET /api/config` (flags only —
  never secrets). Gate a module's routes with
  `require_feature("<key>")` from `feature_flags/interface/deps.py`
  (404 `ERR_FLAG_002` when off) and its frontend routes/nav with
  `<RequireFeature flag>` / `useFeature` from `features/config`.
- Storage: always use `app.core.storage` / `get_file_storage()`; build new
  keys only with `org_key` / `user_key`. `STORAGE_PROVIDER=local` uses
  `MEDIA_DIR`; `s3` selects the S3-compatible adapter. User uploads go through
  the files slice (slot → PUT → confirm), currently user-owned avatars only.
- Plans: `billing/domain/value_objects.py` owns `PLANS`; subscriptions belong
  to organizations, independently of user-level community subscriptions.
  Plan webhooks re-read Stripe, including under the org lock; changes and
  cancellation go through the Customer Portal. `backend/scripts/stripe_sync.py`
  prints `STRIPE_PRICE_PLAN_PRO_MONTHLY`, `STRIPE_PRICE_PLAN_PRO_ANNUAL`,
  `STRIPE_PRICE_PLAN_TEAM_MONTHLY`, and `STRIPE_PRICE_PLAN_TEAM_ANNUAL` env lines.
  Monthly allowance follows the effective plan; Free falls back to
  `MONTHLY_ALLOWANCE_CREDITS`. Grants are lazy per calendar month and carry
  over; upgrades top up the allowance difference idempotently. Credit packs
  remain top-ups on any plan.
- Entitlements: `entitlements/domain/entities.py` owns `PLAN_ENTITLEMENTS`:
  null = unlimited, 0 = excluded, positive n = capacity. Use
  `require_entitlement` from `entitlements/interface/deps.py` for inclusion;
  capacity-consuming use cases call `ensure_within_limit` in the same
  transaction as the write. Unexpired, audited superuser overrides win over
  plan defaults. Entitlements are org-specific limits; feature flags are
  global runtime module switches, and both gates must allow a feature.
- Product analytics: two sinks behind one facade — see docs/analytics.md.
  Frontend call sites import ONLY `track`/`EVENTS` from
  `shared/lib/{track,events}` (never `shared/lib/analytics`, the GA sink) and
  fire once at the success point (mutation hook `onSuccess`). Server-truth
  events (purchases, generation outcomes) are written by the backend through
  a slice-local `ActivityTracker` port satisfied by
  `build_activity_tracker(session)` from `analytics/interface/deps.py` — call
  `capture_server_event(user_id, "<name>", {...})` with a literal name inside
  the transaction that establishes the fact. Every name lives in
  `shared/events.toml` (client vs server tables; run `gen_events.py`).
  Properties are identifiers/enums/numbers only — never prompts, message
  text, emails, or tokens. `activity_events(user_id, created_at)` is an
  external contract: never rename. Adding a data category or changing
  retention (`[analytics]` in policy.toml) means editing
  `features/legal/PRIVACY_POLICY.md` in the same change.
- Community (flag `community`, off by default): platform-level member
  community in `domains/community` — profiles + directory (free), 1:1 DMs
  (premium, polling-based), superuser moderation at `/admin/community`
  (deliberately NOT flag-gated). Premium is a **user-level** Stripe
  subscription: the customer id lives on `community_memberships`, NOT on the
  org's `BillingAccount`; plans/prices in `community/domain/value_objects.py`
  (synced via `stripe_sync.py`, env `STRIPE_PRICE_COMMUNITY_*`); webhook
  events dispatch through `SyncBillingEvent` → the community slice's
  `ApplyCommunitySubscriptionEvent`. `past_due` keeps premium for
  `[community].premium_grace_days` (policy.toml) past the paid-through date.
- Tenancy: every tenant-scoped table has `organization_id`; every
  `/orgs/{org_id}/...` endpoint uses `CurrentMember`/`CurrentAdmin`/`CurrentOwner`
  from `app.domains.organizations.interface.deps`; repositories always filter
  by `organization_id`.
- Services never commit — `get_db` wraps each request in a transaction;
  use `flush()` to obtain ids.
- Errors: raise `AppError` subclasses (define slice-specific ones in the
  slice's `domain/errors.py`). Every class needs an `internal_code` (`ERR_<DOMAIN>_<NNN>`)
  defined in `shared/errors.toml` — the single source of truth for status,
  severity, UX copy, display routing, and retry policy. After editing the
  catalog run `python3 scripts/gen_errors.py`; contract tests fail on drift.
  Handlers in `app.core.error_handling` render RFC 9457 problem+json with a
  correlation id (`instance` / `X-Request-ID`); full request context is kept
  in Redis for 7 days and is resolvable via `GET /api/admin/errors/{error_id}`
  (superuser). Codes are permanent — deprecate, never reuse. Frontend: throw
  nothing manually; `shared/api` normalizes everything into a catalog-aware
  `ApiError` (use `err.userMessage` / `err.actionStep` / `err.fields` in forms;
  toasts/banners/maintenance takeover are global via `lib/errors.tsx`).
  Mutating requests carry an `Idempotency-Key` reused across retries.
  Envelope extras every client reads: `retryable`/`retry_after_ms`, and
  `params` — raise `SomeError(msg, params={...})` with names declared in the
  code's catalog `params` list to fill its `user_message_specific` (clients
  fall back to the generic `user_message` if any value is missing; params are
  ids/numbers only). Validation `fields` carry plain-language copy
  (`friendly_field_message`) — write custom `ValueError`s as user-facing text.
  Show errors inline with `<ErrorAlert error={err} />` (mobile: `<ErrorNote>`);
  rendering it, `getErrorMessage()`, or a matching `isApiErrorWithCode()`
  claims the error so the global toast doesn't duplicate it. Background-job
  failures expose a catalog `error_code`, never raw exception text.
- Background jobs: Celery tasks go in the slice's `tasks.py` (autodiscovered).
  Two queues — `default` (short, latency-sensitive) and `heavy` (long-running);
  pick one via `@celery_app.task(queue=...)`. Tasks must be idempotent
  (`acks_late` re-delivers on worker death) and call async code through
  `run_async` from `app.core.celery_app`. Schedules go in `beat_schedule`.
- Metered AI actions go through the credit engine (`domains/credits`):
  reserve before the provider call, capture on a delivered result, release on
  failure. In-request flows build an engine via `build_credit_engine` from
  `app.domains.credits.interface.deps` and use the `hold_credits` context
  manager from `app.domains.credits.application.facade`; flows spanning
  transactions (Celery jobs) call `CreditEngine.reserve` in the request and
  `capture`/`release` from the job (see `domains/generations`). Costs, hold
  TTLs, packs, and the Free allowance fallback live in
  `domains/credits/domain/value_objects.py`; paid allowances live in the billing
  plan catalog. Stale holds expire and allowances
  grant lazily on wallet touch; a beat task (`credits/tasks.py`) additionally
  sweeps expired holds every 10 minutes so dormant orgs get refunds too.
- Email: always send through `app.core.email` (`send_email` +
  `subscribe_to_marketing_list`/`unsubscribe_from_marketing_list`) — never
  import a provider module directly. Calls are best-effort (logged, never
  raised). Providers implement `EmailProvider` in `app/core/email/` and are
  selected by `EMAIL_PROVIDER` (smtp = Mailpit dev default, resend = prod).
  Compose message copy in the slice's infrastructure (e.g.
  `domains/auth/infrastructure/email_content.py`) using `render_email` from
  `app.core.email.layout`. GDPR: marketing-list calls only for users with
  `marketing_opt_in=True`; transactional email needs no opt-in.
- New `infrastructure/orm.py` modules must be imported in `alembic/env.py`
  for autogenerate. Table/index names are defined there; changing the domain
  entities never changes the schema by itself.
- Cross-slice imports go through a slice's `domain/` (entities, errors) or
  `interface/deps.py` (FastAPI deps, engine builders) only. When a slice needs
  another slice's behavior in its use cases, define a minimal Protocol in its
  own `application/ports.py` and let the other slice's object satisfy it
  structurally (see generations' `CreditService` port).
- DigitalOcean resources are named `[env]-[app]-[service]` (`prd-<app>-db`,
  `stg-<app>-cache`, …) — see NAMING.md before provisioning anything.

## Design system

Read [DESIGN.md](../DESIGN.md) before making visual or UI changes. Font
choices, colors, spacing, and aesthetic direction are defined there; propose
changes to it explicitly rather than deviating in a single component.
