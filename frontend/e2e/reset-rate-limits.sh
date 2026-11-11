#!/usr/bin/env bash
# Clear slowapi rate-limit counters in Valkey so repeated local E2E runs don't
# trip the auth throttles (register 10/h, login 5/min, forgot-password 5/h).
# Deletes only the limiter's LIMITS:* keys — Celery/broker/error-context/
# idempotency keys are untouched.
set -euo pipefail
cd "$(dirname "$0")/../.."
docker compose exec -T valkey sh -c '
  count=0
  for key in $(redis-cli --scan --pattern "LIMITS:*"); do
    redis-cli del "$key" >/dev/null
    count=$((count + 1))
  done
  echo "cleared $count rate-limit counters"
'
