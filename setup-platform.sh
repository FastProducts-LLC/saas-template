#!/usr/bin/env bash
# setup-platform.sh — one-time droplet bootstrap for the shared platform.
# Run ON the droplet. Idempotent: safe to run again.
# Creates the shared network, the /opt/prd-shared tree, and locked-down
# placeholder secret files. Edit each secret file before the first deploy.
# The names below must match docker-compose.prod.yml (network
# prd-shared-backend) and scripts/rollout.sh / the deploy workflow
# (/opt/prd-shared).
set -euo pipefail

NETWORK="prd-shared-backend"
APPS=(myapp)

ROOT="/opt/prd-shared"

# 1. Shared external network (Caddy + all apps live here).
if ! docker network inspect "${NETWORK}" >/dev/null 2>&1; then
  docker network create "${NETWORK}"
  echo "Created network ${NETWORK}"
else
  echo "Network ${NETWORK} already exists"
fi

# 2. Directory tree.
mkdir -p "${ROOT}/caddy.d" "${ROOT}/env"

# 3. Shared platform config file (populate before deploying).
if [ ! -f "${ROOT}/.env.prod" ]; then
  {
    printf '# Shared platform config — populate before first deploy.\n'
    printf '# Apps are separate compose projects; Caddy lives in the prd-shared project.\n\n'
    printf '# --- Redis DB index registry (matches backend/app/core/config.py) ---\n'
    printf '# myapp: /0 (app cache), /1 (celery broker), /2 (celery results)\n'
  } > "${ROOT}/.env.prod"
fi
chmod 600 "${ROOT}/.env.prod"

# 4. Per-app placeholders (deploy pin + per-app secret file).
for app in "${APPS[@]}"; do
  deploy_file="${ROOT}/.env.${app}-deploy"
  [ -f "${deploy_file}" ] || printf 'APP_SHA=stable\n' > "${deploy_file}"
  chmod 600 "${deploy_file}"

  env_file="${ROOT}/env/${app}.env"
  [ -f "${env_file}" ] || printf '# Secrets for %s — populate before first deploy\n' "${app}" > "${env_file}"
  chmod 600 "${env_file}"
done

echo ""
echo "Done. Next steps:"
echo "  1. Populate ${ROOT}/.env.prod and ${ROOT}/env/myapp.env"
echo "  2. Copy Caddyfile, caddy.d/, docker-compose.prod.yml, docker-compose.myapp.yml,"
echo "     scripts/rollout.sh and deploy.sh to ${ROOT}/"
echo "  3. DNS: A record your-domain.com → droplet IP (wait for propagation)"
echo "  4. Bring up Caddy: cd ${ROOT} && docker compose -f docker-compose.prod.yml up -d caddy"
echo "  5. Push to main → CI deploys the app"
