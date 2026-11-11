# Monitoring & Incident Response

External uptime monitoring plus the process for when it fires. Companion to
[runbook.md](runbook.md) (how to operate/debug the stack) and
[backups.md](backups.md) (data durability). Keep postmortems alongside this
file so the incident process and its history live in one place.

## What to monitor

### 1. Uptime check (external)

Point an external checker at the health endpoint:

```
https://your-domain.com/api/health
```

`/api/health` verifies the database (`SELECT 1`) on every call — the same
gate the zero-downtime deploy uses. A 200 means Caddy, the backend, and
Postgres are all alive. It does **not** cover:

- **Valkey/Redis** — the site stays up but degraded without it: idempotency
  fails open, while rate limiting and login lockout fall back to weaker
  per-process in-memory counters (never fully open).
- **Celery workers/beat** — background jobs (emails, generations, retention
  purges) queue up silently. Check with
  `$C exec worker celery -A app.core.celery_app inspect ping` (see
  [runbook.md § Celery](runbook.md)).

**DigitalOcean Uptime** (recommended — same account, ~$1/mo per check):

```bash
doctl monitoring uptime create prd-myapp-health \
  --target https://your-domain.com/api/health --type https --regions us_east
doctl monitoring uptime alert create <check-id> --name prd-myapp-down \
  --type down --comparison less_than --threshold 1 --period 2m \
  --emails you@example.com
```

Add a `latency` alert (e.g. > 1000 ms over 5 min) and an `ssl_expiry` alert
(< 14 days) on the same check. Alternatives if you want status pages or
richer alerting: Better Stack, UptimeRobot — same target URL.

### 2. Resource alerts (DigitalOcean)

In the DO control panel (Monitoring → Alerts), or `doctl monitoring alert
create`, on the droplet and managed DB:

- Droplet CPU > 80% for 10 min, memory > 90% for 10 min, disk > 85%.
- Managed Postgres: disk > 80%, CPU > 90% for 15 min.

### 3. Error tracking (already wired)

Sentry activates when `SENTRY_DSN` is set (backend + frontend + worker; PII
scrubbed). Set up a Sentry alert rule for new issues and error-rate spikes —
that's the signal for SEV3s that never trip the uptime check.

### 4. Security signals

The audit trail (`GET /api/admin/audit-events`, superuser) records logins,
lockouts, password changes, and purchases. A spike of
`auth.lockout_triggered` events = credential-stuffing; group by `ip` and
consider a firewall block. `shared/errors.toml` carries per-code `alert`
notes for the errors worth paging on.

## Incident response

### Severity levels

| Level | Definition | Examples | Response |
|-------|-----------|----------|----------|
| SEV1 | Site down or data at risk | health check failing, DB unreachable, data leak | Drop everything, all hands |
| SEV2 | Major function broken, site up | checkout failing, logins erroring, workers dead | Fix within hours |
| SEV3 | Degraded, workaround exists | slow pages, one provider erroring, elevated error rate | Fix within days |

### Response steps

1. **Acknowledge** the alert (so it's owned, not assumed).
2. **Assess**: open [runbook.md § Common failures](runbook.md) — symptom →
   cause table — and § Health-gate debugging. `$C ps` and
   `$C logs backend --since 15m` answer most "what changed" questions.
3. **Mitigate first, diagnose later**: a bad deploy rolls back with
   `./deploy.sh --rollback` (see runbook); a dead container restarts with
   `$C up -d <service>`. Restoring service beats finding root cause.
4. **Communicate**: if users are affected, note it where they'll see it
   (status page / support email) — silence costs more trust than the outage.
5. **Postmortem** (SEV1/SEV2, within a week): blameless, using the template
   below, committed to `docs/postmortems/YYYY-MM-DD-slug.md`.

### Where evidence lives

- `deploys.log` + `.myapp/last-good-sha` on the droplet — what shipped when.
- `audit_events` table — security events (retained `AUDIT_RETENTION_DAYS`).
- Sentry — stack traces with correlation IDs; `GET /api/admin/errors/{id}`
  resolves a user-reported error ID to full request context (7 days).
- DO monitoring graphs — resource history around the incident window.

### Postmortem template

```markdown
# YYYY-MM-DD — <title>  (SEV<n>)

**Impact**: who/what was affected, for how long.
**Timeline** (UTC): detection → mitigation → resolution, timestamped.
**Root cause**: the actual mechanism, not "human error".
**What went well / what didn't**: detection speed, runbook gaps.
**Actions**: each with an owner and a date; link issues.
```
