#!/usr/bin/env bash
# scripts/rollout.sh — zero-downtime rolling replace for one myapp compose service.
# Runs ON the droplet (SCP'd there by .github/workflows/deploy-myapp.yml).
#
# Why this exists: docker compose (verified on v5.1.3) silently IGNORES
# deploy.update_config.order — it is a Swarm-only key. A plain `up -d` on an
# image change is stop-first: the old container is destroyed BEFORE the new one
# starts, taking the service down for the container's full warmup (~35s
# measured for the backend). So instead:
#
#   1. Start an EXTRA replica of the service on the new image (--scale N+1
#      --no-recreate leaves the old container untouched).
#   2. Wait for the new replica's own healthcheck to report healthy.
#      If it never does, remove it and exit 1 — the old replica was never
#      touched and keeps serving. Failed deploys cause zero downtime.
#   3. Drain the old replica (SIGTERM + grace) and remove it.
#
# Caddy routes around both edges of the swap: `dynamic a` upstreams re-resolve
# Docker DNS every 3s (each replica IP is a separate upstream), passive
# fail_duration benches a dead/not-yet-ready IP, and lb_try_* retries the
# request on the surviving IP. See caddy.d/myapp.caddy.
#
# Usage: rollout.sh <service> [drain-seconds]
#   drain-seconds: how long the old container gets to finish in-flight work
#   before SIGKILL (30 for HTTP services, longer for Celery workers).
set -euo pipefail

SVC="${1:?Usage: rollout.sh <service> [drain-seconds]}"
DRAIN="${2:-30}"
# Must exceed the service's start_period + interval*retries or a healthy-but-slow
# replica gets aborted mid-warmup.
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"

cd /opt/prd-shared
compose() {
  docker compose -f docker-compose.myapp.yml --env-file .env.myapp-deploy "$@"
}

old_ids=$(compose ps -q "$SVC" | tr '\n' ' ')
old_count=$(echo "$old_ids" | wc -w | tr -d ' ')

if [ "$old_count" -eq 0 ]; then
  echo "==> $SVC: not running, plain start"
  compose up -d --wait --wait-timeout 120 --no-deps "$SVC"
  exit 0
fi

echo "==> $SVC: starting new replica alongside $old_count running"
compose up -d --no-deps --no-recreate --scale "$SVC=$((old_count + 1))" "$SVC"

new_id=""
for id in $(compose ps -q "$SVC"); do
  case " $old_ids " in
    *" $id "*) ;;
    *) new_id="$id" ;;
  esac
done
if [ -z "$new_id" ]; then
  echo "ERROR: $SVC: compose did not create a new replica"
  exit 1
fi

abort_new_replica() {
  echo "ERROR: $SVC: new replica is '$1' — aborting; OLD replica keeps serving"
  docker logs --tail 30 "$new_id" 2>&1 || true
  docker rm -f "$new_id" >/dev/null 2>&1 || true
  exit 1
}

echo "==> $SVC: waiting for new replica ${new_id:0:12} to pass its healthcheck"
deadline=$((SECONDS + HEALTH_TIMEOUT))
while :; do
  status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$new_id")
  case "$status" in
    healthy) break ;;   # healthcheck passed
    running) break ;;   # no healthcheck defined — running is the best signal we have
    unhealthy|exited|dead) abort_new_replica "$status" ;;
  esac
  [ "$SECONDS" -ge "$deadline" ] && abort_new_replica "$status after ${HEALTH_TIMEOUT}s"
  sleep 3
done

echo "==> $SVC: new replica healthy; draining old (up to ${DRAIN}s)"
# shellcheck disable=SC2086  # old_ids is a space-separated list of container ids
docker stop -t "$DRAIN" $old_ids >/dev/null
# shellcheck disable=SC2086
docker rm $old_ids >/dev/null
echo "==> $SVC: rollout complete"
