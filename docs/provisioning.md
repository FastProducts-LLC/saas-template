# Provisioning — First-Time DigitalOcean Setup

One-time setup to stand up production on DigitalOcean. This is the documented
reference path, not a requirement: any Linux host with Docker works the same
way, with your own Postgres/Valkey in place of the managed ones. For day-to-day operations
see [runbook.md](runbook.md); for data durability see [backups.md](backups.md).

## How production is laid out

One shared droplet hosts a **platform stack** and one compose project per app:

- **`docker-compose.prod.yml`** — the shared base (compose project
  `prd-shared`): Caddy only, the sole 80/443 entrypoint. One per droplet,
  shared by every app, never renamed per app.
- **`docker-compose.myapp.yml`** — this app's standalone compose project
  (`name: myapp`): `myapp-backend`, `myapp-frontend`, `myapp-worker`,
  `myapp-worker-heavy`, `myapp-beat`. Joins the external
  `prd-shared-backend` network so Caddy can reach it.
- **`caddy.d/myapp.caddy`** — the app's vhost, mounted into Caddy via
  `import sites/*.caddy` in the shared `Caddyfile`.
- Deploys are **zero-downtime** via `scripts/rollout.sh` (scale-based rolling
  replace) — see [runbook.md](runbook.md). CI drives this from
  [.github/workflows/deploy-myapp.yml](../.github/workflows/deploy-myapp.yml).

Everything lives in **`/opt/prd-shared`** on the droplet:

```
/opt/prd-shared/
├── docker-compose.prod.yml    # shared base: Caddy (project prd-shared)
├── docker-compose.myapp.yml   # app project (SCP'd by CI on each deploy)
├── Caddyfile                  # shared snippets + `import sites/*.caddy`
├── caddy.d/myapp.caddy        # app vhost (SCP'd by CI on each deploy)
├── .env.prod                  # shared platform config (Redis DB registry, …)
├── .env.myapp-deploy          # APP_SHA image pin (written by CI / deploy.sh)
├── env/myapp.env              # app secrets (env_file for all app services)
├── scripts/rollout.sh         # zero-downtime rolling replace
├── deploy.sh                  # manual deploy / rollback entrypoint
└── .myapp/                    # CI state: rollout.sh copy, last-good-sha, vhost backup
```

Env split: **`.env.prod`** holds shared, compose-level platform config;
**`env/myapp.env`** holds the app's secrets (`DATABASE_URL`, Stripe, Resend, …)
and is loaded via `env_file:` by every service in `docker-compose.myapp.yml`;
**`.env.myapp-deploy`** pins the image SHA (`APP_SHA=…`).

## Prerequisites

- A DigitalOcean account and a registered domain.
- Pick the **app slug** (lowercase, ≤12 chars) — app resources are named
  `[env]-[app]-[service]` per [NAMING.md](../NAMING.md). The template's
  placeholder slug is `myapp`; substitute yours.
- Create the resources in this order so the VPC ties everything together:
  pick a region → VPC → droplet + managed DB + managed Valkey all attached to
  that VPC.

## 1. Droplet (shared, e.g. `prd-shared-host`)

1. Create a droplet in your region, attached to the VPC. It can host several
   apps behind the one Caddy.
2. Install Docker + the Compose plugin (`get.docker.com`).
3. Run the bootstrap script (idempotent):

   ```bash
   ./setup-platform.sh
   ```

   It creates the `prd-shared-backend` network, the `/opt/prd-shared` tree
   (`caddy.d/`, `env/`), and locked-down placeholder files for `.env.prod`,
   `.env.myapp-deploy`, and `env/myapp.env`.
4. Copy the deploy artifacts into `/opt/prd-shared/`: `docker-compose.prod.yml`,
   `docker-compose.myapp.yml`, `Caddyfile`, `caddy.d/myapp.caddy`,
   `scripts/rollout.sh`, and `deploy.sh` (`chmod +x deploy.sh scripts/rollout.sh`).
   Images come from GHCR; CI refreshes the compose overlay, vhost, and rollout
   script on every deploy.

## 2. Managed Postgres (`prd-myapp-db`)

1. Create a managed Postgres cluster attached to the VPC.
2. Create the logical database `myapp_prod`.
3. **Restrict trusted sources** to the droplet (or the VPC) — never leave it
   open to the public internet.
4. Grab the connection string for `DATABASE_URL` (note the template uses the
   `postgresql+asyncpg://` driver prefix).

## 3. Managed Valkey (`prd-myapp-cache`)

1. Create a managed Valkey (Redis-compatible) cluster, attached to the VPC.
2. Restrict trusted sources to the droplet/VPC.
3. Grab the connection string — it will be `rediss://` (TLS). The app uses
   three logical DBs (allocation in `backend/app/core/config.py`):
   `/0` app cache (`REDIS_URL`), `/1` celery broker (`CELERY_BROKER_URL`),
   `/2` celery results (`CELERY_RESULT_BACKEND`). **All three vars are
   required** — celery does not derive its URLs from `REDIS_URL`. The
   `rediss://` TLS handshake for the broker/backend is handled in
   `backend/app/core/celery_app.py`; no extra params are needed.

## 4. Env files

On the droplet, in `/opt/prd-shared`:

```bash
# app secrets (template: env/myapp.env.example in the repo)
vim env/myapp.env      # chmod 600
# shared platform config (template: .env.prod.example)
vim .env.prod          # chmod 600
```

Required in `env/myapp.env`:

| Var | What |
|-----|------|
| `APP_NAME` | Product name (emails, API docs title). |
| `SECRET_KEY` | Long random string, **≥32 bytes** (`openssl rand -hex 32`). |
| `SECRET_KEY_PREVIOUS` | Optional, rotation only: the former `SECRET_KEY`. Tokens signed with it keep verifying (it never signs). Remove ~48h after rotating. |
| `DATABASE_URL` | Managed Postgres string from step 2. |
| `REDIS_URL` | Managed Valkey `rediss://…/0` string from step 3. |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Same Valkey host, `/1` and `/2`. |
| `FRONTEND_URL` | `https://<your-domain>`. |
| `CORS_ORIGINS` | JSON list, e.g. `["https://your-domain.com"]`. |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, the `STRIPE_PRICE_CREDITS_*` pack ids and `STRIPE_PRICE_PLAN_*` org-plan ids printed by `backend/scripts/stripe_sync.py`; `STRIPE_PRICE_COMMUNITY_*` for community subscriptions. |
| Email | `EMAIL_PROVIDER=resend` + `RESEND_API_KEY` (or real SMTP creds). |

(See `env/myapp.env.example` for the full annotated list, including AI provider
keys and `SENTRY_DSN`.)

The domain itself is not an env var — it's written in `caddy.d/myapp.caddy`
(replace `your-domain.com`) and in the workflow's public health-gate URL.

## 5. DNS

Create an **A record** for your domain pointing at the droplet's public IP
(plus `www` if you keep the redirect block in the vhost). Caddy then provisions
TLS automatically via Let's Encrypt on first boot — no manual cert steps.
Ports 80 and 443 must be reachable.

Bring up Caddy once DNS resolves:

```bash
cd /opt/prd-shared
docker compose -f docker-compose.prod.yml up -d caddy
```

## 6. GitHub Actions config

The deploy workflow
([.github/workflows/deploy-myapp.yml](../.github/workflows/deploy-myapp.yml))
builds + tests + pushes images, SCPs `docker-compose.myapp.yml`,
`caddy.d/myapp.caddy`, and `scripts/rollout.sh` to `/opt/prd-shared`, then
SSHes in and runs the rolling deploy. Configure:

**Secrets** (Settings → Secrets and variables → Actions → Secrets):

- `DROPLET_HOST` — droplet public IP / hostname
- `DROPLET_USER` — SSH user
- `DROPLET_SSH_KEY` — private key for that user

**Repo variables** (same page → Variables, optional):

- `VITE_SENTRY_DSN`, `VITE_GA_MEASUREMENT_ID` — inlined into the frontend
  build; empty leaves those integrations disabled.

The public health gate and `:stable` promotion run against
`https://your-domain.com/api/health` — update the URL in the workflow when you
set your domain.

## 7. First deploy + verify

Push to `main` (the workflow deploys automatically), or on the droplet:

```bash
cd /opt/prd-shared
./deploy.sh stable     # or a specific <git-sha>
```

Then verify:

- `curl -fsS https://<your-domain>/api/health` returns OK.
- The frontend loads in a browser over HTTPS with a valid cert.
- `docker compose -f docker-compose.myapp.yml --env-file .env.myapp-deploy ps`
  shows all five app services `(healthy)`.

## 8. Monitoring

Set up the external uptime check and resource alerts now, while the health
endpoint is fresh in mind — see [monitoring.md](monitoring.md) for the
`doctl monitoring uptime` commands, alert thresholds, and the incident
process behind them.

## Object storage and subscription setup

Create a private Spaces bucket in your chosen region, named
`prd-<app>-assets` (or `stg-<app>-assets`) per [NAMING.md](../NAMING.md).
Use that document's region suffix rule if the name is unavailable. Provision
credentials with access to read, write, inspect, and delete objects in that
bucket; keep them in the backend environment, never in browser configuration.

| Setting | Meaning |
|---------|---------|
| `STORAGE_PROVIDER` | `local` (default) or `s3` for Spaces/S3-compatible storage |
| `MEDIA_DIR` | Local storage root and migration source |
| `S3_BUCKET` | Required for `s3`; the bucket name above |
| `S3_REGION` | Required for `s3`; the bucket region |
| `S3_ENDPOINT_URL` | Spaces regional API endpoint; optional for AWS S3 |
| `S3_ACCESS_KEY_ID` | Required for `s3`; provider access key |
| `S3_SECRET_ACCESS_KEY` | Required for `s3`; provider secret key |

Apply the same storage configuration to the API and workers. Keep the bucket
private: avatar content is served through an unguessable API link, redirecting
to a temporary signed GET under S3; other objects do not need public ACLs.

Configure **bucket CORS** to allow the web app's exact origins to issue `PUT`
requests with the `Content-Type` header. Clients send the headers returned by
the upload slot. API `CORS_ORIGINS` alone does not permit direct browser PUTs
to the bucket. Verify upload, confirmation, and image display from each
allowed origin. S3 PUT signatures do not cap body size; the API checks size
and image signature during confirmation and rejects invalid uploads.

For org billing, set `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET`, then run
`python backend/scripts/stripe_sync.py` in the configured backend environment.
Install its `STRIPE_PRICE_PLAN_PRO_MONTHLY`, `STRIPE_PRICE_PLAN_PRO_ANNUAL`,
`STRIPE_PRICE_PLAN_TEAM_MONTHLY`, and `STRIPE_PRICE_PLAN_TEAM_ANNUAL` values.
Run `python backend/scripts/stripe_sync.py --check`; unset intervals are
reported as disabled, so also verify all intended intervals are configured.
Configure the Customer Portal's allowed plan changes and period-end
cancellation. Send `checkout.session.completed`, `customer.subscription.created`,
`customer.subscription.updated`, and `customer.subscription.deleted` to
`POST /api/billing/webhook`. Use matching Stripe account/mode keys and prices.
