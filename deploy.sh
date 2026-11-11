#!/usr/bin/env bash
# Manual deploy for myapp — run ON the production droplet from /opt/prd-shared.
# (CI is the normal path: .github/workflows/deploy-myapp.yml deploys over SSH
# on every push to main. CI additionally gates on the freshly copied Caddy
# vhost — restoring the last-good one on validation failure — and on the
# public URL through Caddy, auto-rolling back to .myapp/last-good-sha if the
# gate fails. This script has neither safety net; prefer CI when possible.)
#
# Usage: ./deploy.sh [sha|--rollback]
#   ./deploy.sh                deploy the :stable tag
#   ./deploy.sh <git-sha>      deploy a specific image SHA
#   ./deploy.sh --rollback     redeploy the previous SHA (deploys.log from
#                              manual deploys, else CI's .myapp/last-good-sha)
#
# Mechanism (see scripts/rollout.sh): docker compose ignores
# deploy.update_config.order (Swarm-only), so a plain `up -d` on an image
# change is a stop-first recreate (~35s downtime). Instead:
#   caddy validate + reload (routing config must be live BEFORE the rolling
#   replace — Caddy lives in the separate prd-shared project) → pull images →
#   alembic migrate (run --rm --no-deps) → scale-based rolling replace via
#   rollout.sh for backend/frontend/worker/worker-heavy → plain recreate for
#   beat (singleton by design; a brief gap is fine).
set -euo pipefail
cd "$(dirname "$0")"

CADDY_CONTAINER="prd-shared-caddy-1"

# Optional shared platform config (compose-level vars; app secrets are in
# env/myapp.env, loaded by the compose file itself).
if [ -f .env.prod ]; then
  set -a; . ./.env.prod; set +a
fi

if [ "${1:-}" = "--rollback" ]; then
  if [ -f deploys.log ] && [ "$(wc -l < deploys.log)" -ge 2 ]; then
    DEPLOY_SHA="$(tail -n 2 deploys.log | head -n 1 | awk '{print $2}')"
    echo "==> Rolling back to previous manual deploy: ${DEPLOY_SHA}"
  elif [ -f .myapp/last-good-sha ]; then
    # deploys.log only records manual runs; CI-deployed droplets have none.
    # last-good-sha is the newest CI deploy that passed the public health
    # gate — if the deploy being rolled back itself passed the gate, this is
    # that same SHA; pass an explicit older SHA instead.
    DEPLOY_SHA="$(cat .myapp/last-good-sha)"
    echo "==> No manual deploy history — rolling back to CI last-good SHA: ${DEPLOY_SHA}"
  else
    echo "ERROR: No previous deploy recorded — neither deploys.log (2+ entries) nor .myapp/last-good-sha exists." >&2
    echo "       Roll back explicitly with ./deploy.sh <old-sha> (find SHAs in GHCR tags)." >&2
    exit 1
  fi
else
  DEPLOY_SHA="${1:-stable}"
fi

# Pin the SHA. rollout.sh re-reads this file on every call.
printf 'APP_SHA=%s\n' "${DEPLOY_SHA}" > .env.myapp-deploy.tmp
mv -f .env.myapp-deploy.tmp .env.myapp-deploy
chmod 600 .env.myapp-deploy

# The app is a standalone compose project (name: myapp) — same invocation as
# CI and scripts/rollout.sh. The shared base (Caddy) is a separate project.
COMPOSE=(docker compose
  -f docker-compose.myapp.yml
  --env-file .env.myapp-deploy)

# rollout.sh: repo copy under scripts/, or the CI-managed copy under .myapp/.
if [ -x scripts/rollout.sh ]; then
  ROLLOUT=scripts/rollout.sh
elif [ -f .myapp/rollout.sh ]; then
  ROLLOUT=.myapp/rollout.sh
else
  echo "ERROR: rollout.sh not found (looked in scripts/ and .myapp/)." >&2
  exit 1
fi
chmod +x "$ROLLOUT"

echo "==> Validating + reloading Caddy (${CADDY_CONTAINER}, prd-shared project)"
# Before the rolling replace, same as CI — routing config must be live during
# the start-first transition.
docker exec "${CADDY_CONTAINER}" caddy validate --config /etc/caddy/Caddyfile
docker exec "${CADDY_CONTAINER}" caddy reload --config /etc/caddy/Caddyfile

echo "==> Pulling images: ${DEPLOY_SHA}"
"${COMPOSE[@]}" pull myapp-backend myapp-frontend

echo "==> Running migrations (must be expand/contract — old code still serves)"
"${COMPOSE[@]}" run --rm --no-deps myapp-backend alembic upgrade head

echo "==> Rolling replace (scale up → health gate → drain old)"
# A failed rollout leaves the OLD replica serving untouched — just aborts.
# Order: backend first (old frontend must never point at a missing new API).
# Drain seconds mirror each service's stop_grace_period.
bash "$ROLLOUT" myapp-backend 30
bash "$ROLLOUT" myapp-frontend 30
bash "$ROLLOUT" myapp-worker 120
bash "$ROLLOUT" myapp-worker-heavy 600

echo "==> Recreating beat (singleton — plain stop-first, gated on health)"
# start_period is 120s (beat replays its schedule in recovery mode), so the
# wait budget must exceed it.
"${COMPOSE[@]}" up -d --wait --wait-timeout 180 --no-deps myapp-beat

"${COMPOSE[@]}" ps
docker image prune -f >/dev/null

printf '%s  %s\n' "$(date -u +%FT%TZ)" "${DEPLOY_SHA}" >> deploys.log
echo "==> Deploy complete: ${DEPLOY_SHA}"
