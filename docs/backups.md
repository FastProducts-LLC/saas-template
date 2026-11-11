# Backups & Restore

What is durable, what is not, and how to rehearse recovery. See
[provisioning.md](provisioning.md) for the managed-service setup and
[runbook.md](runbook.md) for day-2 ops.

## What holds the data

| Store | Service | Backed up? |
|-------|---------|------------|
| Postgres | `prd-<app>-db` (managed) | **Yes** — DO automated backups + PITR. |
| `media` volume | Docker volume on the droplet | **No** — not covered by DB backups. |
| Valkey | `prd-<app>-cache` (managed) | **No** — ephemeral by design. |

## Postgres (`prd-<app>-db`)

DigitalOcean managed Postgres takes **automated daily backups** and supports
**point-in-time recovery (PITR)** to any moment within the retention window.
Nothing to configure on the app side — it's on by default for managed clusters.

Check retention and the latest backup:

```bash
doctl databases backups list <cluster-id>
```

(or DO console → the cluster → **Backups** tab). PITR lets you fork/restore to a
specific timestamp inside the retained range — useful for recovering from a bad
migration or an accidental delete.

### Restore drill (rehearse periodically)

Don't wait for an incident to learn the restore path. Periodically:

1. **Restore to a fork** — create a new cluster from a backup / PITR timestamp
   (DO calls this a "fork"): `doctl databases fork`, or the console's
   **Restore / Fork** action. Never restore over production.
2. **Point a staging `.env` at it** — set `DATABASE_URL` in a staging
   `.env.prod` to the forked cluster's connection string.
3. **Verify** — run the staging stack, hit `/api/health` (it checks the DB),
   and spot-check that recent data is present and migrations are at `head`.
4. **Destroy the fork** — delete the forked cluster so it stops billing.

Record how long the drill took — that's your real RTO.

## The `media` volume

Generated assets (images/video the worker writes under `settings.media_dir`)
live in the `media` Docker volume on the droplet. This is **not** in the DB
backups — if the droplet dies, the assets are gone.

Two options, in order of durability:

**A. Recommended — migrate media to Spaces.** Store generated assets in a
Spaces bucket (`prd-<app>-assets`) instead of a local volume. Spaces is durable
object storage with its own redundancy, and it survives droplet loss entirely.

**B. Interim — periodic tar snapshot to Spaces.** While media is still on the
volume, snapshot it on a schedule:

```bash
# Snapshot the media volume to a tarball and push to Spaces (needs s3cmd/aws configured)
docker run --rm -v myapp_myapp_media:/media -v /tmp:/backup alpine \
  tar czf /backup/media-$(date -u +%F).tar.gz -C /media .
s3cmd put /tmp/media-$(date -u +%F).tar.gz s3://prd-<app>-backups/media/
```

(`myapp_myapp_media` = compose project `myapp` + volume key `myapp_media` in
`docker-compose.myapp.yml`; confirm with `docker volume ls`.)

## Valkey (`prd-<app>-cache`)

Valkey is **ephemeral** — it holds the Celery broker queue, task results, and
rate-limit counters, none of which is a source of truth. No backup is needed.

Losing Valkey drops queued/in-flight tasks. That's acceptable: tasks are
idempotent (`acks_late`), credit holds for failed/lost jobs expire and refund
automatically, and users can simply retry. Rate-limit counters reset harmlessly.
