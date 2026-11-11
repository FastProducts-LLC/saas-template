# Runbook — Day-2 Operations

Operating the production stack on the shared droplet. Everything runs from
**`/opt/prd-shared`** (the directory holding `docker-compose.prod.yml`,
`docker-compose.myapp.yml`, `Caddyfile`, `caddy.d/`, `deploy.sh`,
`scripts/rollout.sh`, `.env.prod`, `.env.myapp-deploy`, `env/myapp.env`).
See [provisioning.md](provisioning.md) for first-time setup,
[backups.md](backups.md) for data durability, and
[monitoring.md](monitoring.md) for uptime alerts + incident response.

Two compose projects live side by side:

- **`prd-shared`** (`docker-compose.prod.yml`) — Caddy only, shared by every
  app on the droplet. Never `down` it.
- **`myapp`** (`docker-compose.myapp.yml`) — this app's five services:
  `myapp-backend`, `myapp-frontend`, `myapp-worker`, `myapp-worker-heavy`,
  `myapp-beat`.

```bash
cd /opt/prd-shared
export C="docker compose -f docker-compose.myapp.yml --env-file .env.myapp-deploy"   # app project shorthand
```

## Deploying

**Automatic (the normal path).** Pushing to `main` triggers
[.github/workflows/deploy-myapp.yml](../.github/workflows/deploy-myapp.yml): it
tests, builds + pushes the backend/frontend images to GHCR, SCPs the compose
overlay / vhost / rollout script to `/opt/prd-shared`, then SSHes in and runs
the rolling deploy. A deploy that passes the public health gate promotes those
images to `:stable` and records the SHA in `.myapp/last-good-sha`; a failed
rollout or health gate auto-rolls-back to the last-good SHA.

**Manual.** On the droplet:

```bash
./deploy.sh <git-sha>   # deploy a specific commit's images
./deploy.sh             # deploy the :stable tag (last known-good)
```

`deploy.sh` pins the SHA in `.env.myapp-deploy`, pulls images, runs
`alembic upgrade head` via `run --rm --no-deps` against the new image while the
old code still serves, then calls `scripts/rollout.sh` per service.

**How the zero-downtime rollout actually works** (`scripts/rollout.sh`):
docker compose silently ignores `deploy.update_config.order` — it's a
Swarm-only key — so a plain `up -d` on an image change is **stop-first** and
takes the service down for its full warmup (~35s measured for the backend).
Instead, rollout.sh scales the service to N+1 (`--no-recreate` leaves the old
container untouched), waits for the **new** replica's own compose healthcheck
to go healthy, then drains and removes the old one. A new replica that never
goes healthy is removed and the script exits 1 — the old replica was never
touched, so failed deploys cause zero downtime. `myapp-beat` is the exception:
it's a singleton (two beats double-fire every schedule), so it gets a plain
stop-first recreate gated on `up -d --wait`.

During the overlap window Caddy routes around both edges of the swap: the
vhost uses `dynamic a` upstreams that re-resolve Docker DNS every 3s, passive
`fail_duration` benches a dead IP, and `lb_try_*` retries in-flight requests
on the surviving replica. Note Caddy does **not** run active health checks
against dynamic upstreams (`health_uri` would be a no-op there — see the
comment in `caddy.d/myapp.caddy`); the compose healthchecks are what gate the
rollout cutover.

Each successful manual deploy appends `<timestamp>  <sha>` to `deploys.log`.

## Rolling back

```bash
./deploy.sh --rollback   # redeploy the previous SHA (see below)
./deploy.sh <old-sha>    # redeploy any specific SHA explicitly
```

`--rollback` reads the second-to-last line of `deploys.log` (manual-deploy
history) and redeploys that SHA through the same rollout.sh path (recording
the rollback as a new deploy entry). On a droplet that has only ever been
deployed by CI, `deploys.log` doesn't exist — `--rollback` then falls back to
`.myapp/last-good-sha`. Note that last-good-sha is the newest CI deploy that
*passed* the health gate, so if the deploy you're reverting passed it, that's
the same SHA — pass an explicit older SHA instead. CI failures roll back
automatically to `.myapp/last-good-sha`. Finding SHAs to roll back to:

- **`deploys.log`** — `tail deploys.log` shows recent `<timestamp>  <sha>` rows
  (manual deploys).
- **`.myapp/last-good-sha`** — the last CI deploy that passed every gate.
- **GHCR tags** — every build is tagged with its long commit SHA; `:stable` is
  the last verified deploy.
- **`.env.myapp-deploy`** — the currently-pinned `APP_SHA` on the droplet.

> **IMPORTANT — rollback reverts images, not schema.** Migrations are
> expand/contract, so rolling code *back* over a *newer* schema is safe (the
> old code simply ignores added columns). But **never roll back across a
> destructive (contract) migration** that dropped/renamed a column the old code
> needs — the old image will crash on the new schema. That case requires a DB
> restore (see [backups.md](backups.md)), not a code rollback.

## Health-gate debugging

A rollout aborts if the new replica never passes its healthcheck — the old
replica keeps serving, so nothing swapped. rollout.sh prints the new replica's
last 30 log lines before removing it; to dig further:

```bash
$C ps                                          # STATUS shows (healthy)/(unhealthy)/(starting)
$C logs --tail 50 --no-color myapp-backend     # or myapp-frontend / myapp-worker / myapp-beat
```

Healthcheck parameters (from `docker-compose.myapp.yml`):

| Service | Probe | interval / timeout / retries / start_period |
|---------|-------|---------------------------------------------|
| myapp-backend | `urllib` GET `http://localhost:8000/api/health` (verifies DB) | 15s / 5s / 3 / 30s |
| myapp-frontend | `wget --spider` `http://127.0.0.1:8080/` | 15s / 5s / 3 / 15s |
| myapp-worker / myapp-worker-heavy | pidfile liveness: `os.kill(<pid from /tmp/celery-worker.pid>, 0)` | 15s / 5s / 3 / 30s |
| myapp-beat | same pidfile check on `/tmp/celery-beat.pid` | 15s / 5s / 3 / 120s (beat replays its schedule in recovery mode before writing the pidfile) |

The worker probe checks that the celery **process is alive** (cheap, no broker
round-trip) — it does *not* prove broker connectivity; use `inspect ping` below
for that. `/api/health` checks the DB connection, so a backend stuck
`unhealthy` after a deploy is usually a `DATABASE_URL` / managed-DB
connectivity problem, not app code. rollout.sh's wait budget is
`HEALTH_TIMEOUT` (default 150s) — it must exceed
`start_period + interval × retries` for the service being rolled.

## Celery operations

Two worker pools: `myapp-worker` (`default` queue — short, latency-sensitive)
and `myapp-worker-heavy` (`heavy` queue — long-running jobs).

```bash
$C exec myapp-worker celery -A app.core.celery_app inspect ping     # workers alive + broker reachable?
$C exec myapp-worker celery -A app.core.celery_app inspect active   # tasks running now
$C exec myapp-worker celery -A app.core.celery_app call app.ping    # round-trip smoke test
```

**Scaling.** Scale workers, never beat:

```bash
$C up -d --no-deps --no-recreate --scale myapp-worker=3 myapp-worker   # more default-queue throughput
```

`myapp-beat` is **single-instance** — two beats double-fire every schedule.
Never scale it past 1.

**Beat schedule** (`backend/app/core/celery_app.py`) — recurring jobs:

- `expire-stale-credit-reservations` — every 10 min; refunds expired credit holds.
- `purge-expired-refresh-tokens` — daily 03:30 UTC; trims the refresh-token table.
- `purge-privacy-request-payloads` — daily 04:15 UTC; drops raw DSAR intake PII past retention.

Verify they fired via the beat scheduler log and the worker's task log:

```bash
$C logs --tail 100 myapp-beat | grep -E "Scheduler: Sending|expire-stale|purge-expired|purge-privacy"
$C logs myapp-worker | grep -E "expire_stale_reservations|purge_refresh_tokens|purge_privacy_request_payloads"
```

## Caddy operations

Caddy belongs to the shared `prd-shared` project — treat it as
platform infrastructure:

```bash
docker exec prd-shared-caddy-1 caddy validate --config /etc/caddy/Caddyfile  # after editing a vhost
docker exec prd-shared-caddy-1 caddy reload --config /etc/caddy/Caddyfile    # zero-downtime config swap
docker compose -f docker-compose.prod.yml logs --tail 50 caddy
```

Never `docker compose -f docker-compose.prod.yml down` — it takes 80/443 (and
TLS) away from **every** app on the droplet.

## Common failures

| Symptom | Cause / fix |
|---------|-------------|
| Deploy aborts at "Running migrations" | A migration failed — the deploy exits **before** any traffic swap, so the old code keeps serving. Fix the migration (forward-fix preferred; expand/contract), re-deploy. No rollback needed — nothing changed. |
| Rollout aborts: "new replica is 'unhealthy'" | New image never passed its healthcheck; old replica still serving. Check the log excerpt rollout.sh printed, fix, re-deploy. |
| Task runs forever / worker probe failing | Hit the time limits in `celery_app.py` (`task_soft_time_limit=540s`, hard kill at 600s). `inspect active` to find it; check the provider/3rd-party call it's blocked on. |
| Backend `unhealthy`, `/api/health` 500s | Managed Postgres unreachable (firewall/trusted-sources, wrong `DATABASE_URL`) or Valkey down (`REDIS_URL`, `rediss://` TLS). Verify the managed clusters and trusted sources. |
| Workers alive but no tasks execute | Broker connectivity — the pidfile healthcheck can't see this. `inspect ping` fails ⇒ confirm `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` are set in `env/myapp.env` (celery does **not** derive them from `REDIS_URL`), use `rediss://`, and the droplet is in the Valkey cluster's trusted sources. |
| TLS cert errors / site not HTTPS | Caddy auto-TLS via Let's Encrypt — check the DNS A record points at the droplet, ports 80/443 are open, and the hostname in `caddy.d/myapp.caddy` is correct. `docker compose -f docker-compose.prod.yml logs caddy`. |
| Disk full / uploads failing | The media volume (`myapp_myapp_media`) filled up with generated assets. `docker system df -v`, prune old images, or migrate media to Spaces (see [backups.md](backups.md)). |

## Moving local media to S3

Provision the bucket and CORS as in [provisioning.md](provisioning.md). Use a
configured backend Python environment with database access and the existing
media mounted at `MEDIA_DIR`. From the repository root:

```bash
python backend/scripts/migrate_media_to_storage.py --dry-run
python backend/scripts/migrate_media_to_storage.py
```

Set `STORAGE_PROVIDER=s3` and the bucket credentials for the script first.
It reads generation rows, preserves stored keys, skips equal-sized destination
objects, and never changes rows or deletes local sources. Review `missing`
as well as `failed` in the summary: missing sources do not cause a nonzero exit.
Equal size is not a checksum verification. Confirm representative downloads
before switching API and workers to the same S3 settings through the normal
deploy process. Quiesce media writes during the final copy and cutover so new
local objects cannot be missed; retain local sources for recovery.

The script only migrates **generation assets**. Existing avatar uploads in
`stored_files` must also be copied preserving their keys before switching;
there is no shipped uploaded-file migration command. The generation `/file`
endpoint continues returning bytes; `/file-url` provides the signed URL for
S3 and returns `url: null` for local storage (use `/file` instead). Check both
after cutover.

## Plan webhooks and revenue drift

For failed plan deliveries, inspect the Stripe delivery response and API logs.
A 400 signature failure means the signing secret or payload verification needs
attention: check `STRIPE_WEBHOOK_SECRET` for that endpoint and Stripe mode.
For provider/database failures, restore connectivity and check
`STRIPE_SECRET_KEY`, then retry the delivery in Stripe. Org plan events require
`org_plan=1` and an organization identifier in metadata; community tags take
precedence. Check that configured plan price ids match the subscription's price.
Unknown prices are logged: existing rows retain their recognized plan, while
new unrecognized subscriptions are ignored. A successful HTTP response alone
does not prove the local plan changed.

After correcting configuration, resend the relevant subscription event and
verify the effective plan in Billing. The handler re-reads current Stripe state,
including under the org lock, rather than replaying stale event state. Changes
and cancellation belong in the Customer Portal. Paid access on `past_due`
lasts 3 days after `current_period_end` (`[billing].plan_grace_days`), then falls
back to Free; fixing payment should produce an updated subscription event.

Run this in the configured backend environment with database and Stripe access:

```bash
python backend/scripts/reconcile_revenue.py --json
```

This is read-only: exit 0 means in sync, 1 means drift, and 2 means
`STRIPE_SECRET_KEY` is missing. Inspect missing subscriptions and status/plan/
interval mismatches; repair the delivery/configuration issue, resend events,
and rerun reconciliation. It does not repair rows or compare invoice totals.
The admin revenue report uses catalog prices: annual amounts divided by 12;
active and past-due subscriptions contribute MRR, trials do not. Reconciliation
also uses catalog prices, so run `python backend/scripts/stripe_sync.py --check`
for actual configured-price drift. Do not treat this report as cash receipts.
