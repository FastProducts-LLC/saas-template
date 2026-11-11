# Design: object storage, subscription plans, and entitlements

Status: implemented; the original design below is retained for context. See
“As built” for differences from the shipped code.

## Why this order

1. **Object storage** — medium effort, and avatars, uploads, and any
   multi-replica deploy depend on it (generation assets live on a local
   `media_dir` volume today).
2. **Subscription plans** — org billing is one-time credit packs only. Plans
   shape the schema and are the hardest thing to retrofit after a product
   forks.
3. **Entitlements** — per-plan gating. Depends on plans existing; every later
   feature is gated through it.
4. **Revenue reporting** — reads the tables the first three create.

Session management and bot protection follow as separate small pieces and are
not designed here.

## Phase 1 — Object storage

**Port.** `app/core/storage/` with a `FileStorage` protocol, selected by
`STORAGE_PROVIDER` the same way `EMAIL_PROVIDER` selects an email provider:

- `local` (dev default): today's disk behaviour, files served through the API.
- `s3` (production): any S3-compatible bucket; DigitalOcean Spaces is the
  documented target. Config validation refuses `s3` without bucket, region,
  endpoint, and keys, mirroring the Resend checks in `core/config.py`.

Operations: `put(key, data, content_type)`, `delete(key)`,
`presigned_get(key, ttl)`, `presigned_put(key, content_type, max_bytes, ttl)`.

**Keys are tenant-scoped**: `org/<org_id>/<area>/<uuid>.<ext>` for org data,
`user/<user_id>/...` for user-level data (community avatars). Callers never
pass a raw key from the client.

**1a — move generations onto the port.** `generations/infrastructure/media_store.py`
becomes a thin adapter over `FileStorage`. `generations.file_path` already
stores a relative path, so it becomes the storage key with no schema change.
`GET .../generations/{id}/file` keeps its URL and auth check; under `s3` it
redirects to a short-lived presigned GET, under `local` it streams as now. A
one-off script copies existing media files into the bucket for deployments
that already have assets.

**1b — user uploads.** New `stored_files` table
(`id, organization_id NULL, user_id NULL, key, content_type, size_bytes, status, created_by_id, created_at`).
Flow: client asks for an upload slot → API validates type and size against
`[uploads]` in `shared/policy.toml` and returns a presigned PUT → client
uploads directly → client confirms → API verifies the object exists and marks
it `ready`. A beat task deletes `pending` rows and objects older than a day.
First consumer: community avatars, which closes the open item in `ROADMAP.md`.

**Also in this phase:** `[uploads]` policy section, new error codes in
`shared/errors.toml`, env examples, `docs/provisioning.md` (bucket naming per
`NAMING.md`), and a privacy-policy edit if uploaded files count as a new data
category.

## Phase 2 — Subscription plans (org level)

**Where it lives.** In the existing `billing` slice. Plans belong to the
organization, like `BillingAccount`, and reuse its Stripe customer. The
community premium subscription stays user-level and untouched.

**Catalog.** `billing/domain/value_objects.py` holds `Plan` (enum) and
`PlanSpec` (name, monthly and annual price, monthly credit allowance),
following the `COMMUNITY_PLANS` pattern. `scripts/stripe_sync.py` creates the
Products and Prices and prints `STRIPE_PRICE_PLAN_<PLAN>_<INTERVAL>` env
lines; `--check` covers them too.

**Schema.** `subscriptions`
(`id, organization_id UNIQUE, stripe_subscription_id, plan, interval, status, current_period_end, cancel_at_period_end, created_at, updated_at`).
No row means the free plan.

**Checkout and changes.** Subscribing uses Stripe Checkout in subscription
mode, tagged `metadata.org_plan=1` plus `organization_id` on both the session
and the subscription — the same technique that tags community checkouts
(`community_membership=1`), so the webhook parser can tell the two apart.
Upgrades, downgrades, cancellation, and payment-method changes go through the
Stripe Customer Portal, which the app already opens. No custom proration UI.

**Webhooks.** `StripeGateway.parse_event` gains org-plan events, dispatched by
`SyncBillingEvent` to a new `ApplyOrgSubscriptionEvent`. To stay correct under
duplicate and out-of-order delivery, the handler does not trust the event
payload's state: it re-reads the subscription from Stripe and writes that.

**Past due.** Paid access continues for `[billing].plan_grace_days`
(policy.toml) after `current_period_end`, the same rule community premium
uses. Canceled falls back to free at period end.

**Credits coexistence.** Packs stay as top-ups on any plan. The single
`MONTHLY_ALLOWANCE_CREDITS` constant is replaced by a lookup of the org's
current plan through a port in the credits slice. The existing behaviour is
kept: granted lazily once per calendar month, added to the balance, and
unused credits carry over.

**Surfaces.** Pricing page plan cards, a current-plan panel on the billing
page with "Manage plan" (portal), server-truth analytics events in
`shared/events.toml` (`plan_subscribed`, `plan_changed`, `plan_canceled`),
audit entries, and a Terms update covering auto-renewal and cancellation.
Mobile shows the current plan read-only and sends users to the web to change
it, which avoids in-app-purchase rules.

## Phase 3 — Entitlements

**New slice** `domains/entitlements`, kept separate from `feature_flags`.
Flags remain global deploy-time switches; entitlements answer "may this org
do this, and how much". A gated feature needs both: flag on, and entitlement
granted.

**Model.** Each plan maps to a set of entitlements in the slice's domain:
booleans (for example `api_access`) and numeric limits (for example `seats`,
`api_keys`). An `organization_entitlements` table
(`organization_id, key, limit_value, source, expires_at`) holds per-org
overrides set by superusers, each change audited. Resolution: unexpired
override first, else the plan default.

**Backend.** The slice reads the org's plan through a port that billing
satisfies. It exports `require_entitlement("<key>")` and a limit check from
`interface/deps.py`; denial raises a new `ERR_ENT_*` error whose catalog entry
carries the upgrade action. Enforcement is always server-side.

**Clients.** `GET /orgs/{org_id}/entitlements` returns a snapshot; web and
mobile get `useEntitlement` and `<RequireEntitlement>`, which shows an upgrade
prompt instead of hiding the feature. `/admin` gets an override editor.

**First gates shipped with the template**, so forks have a working example:
member count (`seats`) on invitations, and API key count.

## Phase 4 — Revenue reporting

Admin view of MRR, active subscriptions by plan, new and churned in period,
computed from the local `subscriptions` table. A reconcile command compares
the local total against Stripe and reports drift; Stripe is the source of
truth.

## Housekeeping per phase

Flip the matching entries in `featureCatalog.ts` from `blueprint` to
`included`; update `docs/conventions.md`, `docs/customization.md`, and the
env examples; add migrations and import new `orm.py` modules in
`alembic/env.py`.

## Testing approach

Use cases are unit-tested with in-memory fakes of the ports, per the repo
convention. Specific cases that must be covered:

- Storage: cross-org key access denied; oversized and wrong-type uploads
  rejected; unconfirmed uploads cleaned up; presigned URL expiry.
- Subscriptions: duplicate webhook; out-of-order webhook; payment failure then
  recovery; grace window boundary; cancel at period end; a community event
  never touching an org subscription and the reverse.
- Entitlements: denied when the plan lacks it; limit reached; override grants;
  expired override falls back to plan; flag off beats entitlement.
- End to end against Stripe test mode in an isolated compose project.

## Open decisions (defaults in use unless changed)

1. **Plan ladder**: Free, Pro, Team, with placeholder prices for forks to edit.
2. **Seats**: flat plan price with a seat *limit* per plan. Per-seat pricing
   (Stripe quantity synced to member count) is deferred.
3. **Trials**: off by default, switchable via `[billing].trial_days`.
4. **Production storage**: DigitalOcean Spaces. No MinIO container in dev;
   dev uses the local adapter.

## As built

- Storage also exposes `get` and `stat`; `S3_ENDPOINT_URL` is optional for AWS.
  Generation `/file` still returns bytes for either provider; the separate
  `/file-url` endpoint returns a temporary S3 URL or null for local storage.
- Only user-owned avatar upload purposes ship. Confirmation checks actual size
  and image signature, not just existence; S3 presigned PUT cannot enforce the
  size ceiling itself. Avatars are public by unguessable link. The migration
  script copies generation assets only. Organization deletion does not delete
  stored objects; avatar deletion is best-effort on provider failures.
- Free retains the credits slice's `MONTHLY_ALLOWANCE_CREDITS` fallback rather
  than removing that constant. Paid allowances come from `PLANS`; upgrades
  top up the allowance difference idempotently in addition to lazy monthly grants.
- Entitlements ship `seats` and `api_keys` with null/0/positive-integer limits,
  no separate `api_access` boolean. Seats include pending unexpired invitations;
  capacity checks also cover joining an organization. Flags are global runtime
  switches. Native screens use `useEntitlements` and helpers rather than the
  web `useEntitlement` / `RequireEntitlement` interface.
- Revenue includes ARR and fixed recent-period counts; MRR counts active and
  past-due subscriptions, excludes trials, and uses catalog prices. Reconciliation
  compares subscription state and catalog MRR, without writing repairs or
  reconciling invoice receipts.
- The three SaaS catalog rows remain `blueprint` until the catalog/test update
  listed in `ROADMAP.md`.
