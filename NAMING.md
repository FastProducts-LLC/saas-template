# DigitalOcean Naming Convention

> Only relevant if you deploy to DigitalOcean, the provider the deploy docs use.
> The app itself has no DigitalOcean dependency.

Every project cloned from this template picks one short **app slug** (lowercase,
hyphens only, ≤12 chars — e.g. `nexus`) and names all DigitalOcean resources:

```
[env]-[app]-[service]
```

- **env** — `dev`, `stg`, `prd` (always this three-letter set, always a prefix)
- **app** — the project slug, same everywhere
- **service** — resource-type suffix from the table below

Rules: always lowercase, hyphens only (no underscores/spaces), no secrets, IPs,
or versions in names, keep the full string under ~30 chars.

## Resource map for this template

| Template piece              | DO resource             | Name (prd example)      |
|-----------------------------|-------------------------|-------------------------|
| App containers (backend + frontend + workers) | Shared droplet (Docker Compose + Caddy) | droplet `prd-shared-host`; compose project `<app>` |
| Postgres (`db` service)     | Managed DB cluster      | `prd-<app>-db`          |
| — logical database          | inside the cluster      | `<app>_prod` (underscores OK internally) |
| — connection pool           | PgBouncer pool          | `prd-<app>-pool`        |
| Valkey (`valkey` service, Valkey 8) | Managed Valkey  | `prd-<app>-cache`       |
| User uploads / assets       | Spaces bucket           | `prd-<app>-assets`      |
| DB backups                  | Spaces bucket           | `prd-<app>-backups`     |
| Network boundary            | VPC                     | `prd-<app>-vpc`         |
| Firewall                    | Cloud Firewall          | `prd-<app>-fw`          |
| Container images            | DOCR repo               | `<app>/backend`, `<app>/frontend` |
| Resource grouping           | DO Project              | `<app>-prd`             |

Mailpit is dev-only — production uses real SMTP credentials, no DO resource.

## Environment matrix

| Resource     | Production         | Staging            | Development        |
|--------------|--------------------|--------------------|--------------------|
| Droplet (shared, multi-app) | `prd-shared-host` | `stg-shared-host` | local Docker Compose |
| DB cluster   | `prd-<app>-db`     | `stg-<app>-db`     | `dev-<app>-db`     |
| Valkey       | `prd-<app>-cache`  | `stg-<app>-cache`  | `dev-<app>-cache`  |
| Spaces       | `prd-<app>-assets` | `stg-<app>-assets` | `dev-<app>-assets` |
| VPC          | `prd-<app>-vpc`    | `stg-<app>-vpc`    | `dev-<app>-vpc`    |

## DNS

| Record           | Host       | Points to             |
|------------------|------------|-----------------------|
| Production app   | `app`      | shared droplet IP (`prd-shared-host`) |
| Staging app      | `stg`      | staging droplet IP    |
| API              | `api`      | backend service       |
| Staging API      | `stg-api`  | staging backend       |
| Spaces CDN       | `cdn`      | `prd-<app>-assets` CDN endpoint |

Point the Stripe production webhook at `https://api.<domain>/api/billing/webhook`
(staging webhook endpoint configured separately against `stg-api.<domain>`).

## DO-specific gotchas

- **Spaces names are region-unique and DNS-compliant** — if `prd-<app>-assets`
  is taken, append the region: `prd-<app>-assets-nyc3`.
- **Pick the region first**, create the VPC, then attach everything to it:

  ```env
  DO_REGION=nyc3
  DO_VPC_NAME=prd-<app>-vpc
  ```

- **Image repos are app-scoped** — the template pushes to GHCR as
  `ghcr.io/<org>/<app>/backend` and `ghcr.io/<org>/<app>/frontend`; the deploy
  pin lives in the tag (a git SHA, plus the `:stable` last-verified alias),
  not the repo name. (If you use DOCR instead, same shape: `<app>/backend`.)
- **Multi-instance / multi-region** — append a zero-padded index
  (`prd-<app>-worker-01`) or insert the region (`prd-<app>-nyc3-db`) only when
  you actually have more than one.

## Deploy target: shared droplet (Docker Compose + Caddy)

The app deploys to a **shared droplet** (`prd-shared-host`) that hosts one
platform stack plus one compose project per app under `/opt/prd-shared`
(see [docs/provisioning.md](docs/provisioning.md)):

- Compose project `prd-shared` (`docker-compose.prod.yml`) — the shared Caddy
  reverse proxy; container `prd-shared-caddy-1`, external network
  `prd-shared-backend`. Platform-owned; never renamed per app.
- Compose project `<app>` (`docker-compose.<app>.yml`) — the app's services,
  prefixed with the slug: `<app>-backend`, `<app>-frontend`, `<app>-worker`,
  `<app>-worker-heavy`, `<app>-beat`.
- Caddy vhost: `caddy.d/<app>.caddy`; deploy pin: `.env.<app>-deploy`;
  app secrets: `env/<app>.env`.
