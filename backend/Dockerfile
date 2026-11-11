FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Deps layer first so code changes don't invalidate it; the cache mount
# keeps uv's download cache warm across builds (works with GHA cache too).
# requirements.txt is a fully pinned lock (uv pip compile pyproject.toml) for
# reproducible builds — regenerate it whenever pyproject.toml changes.
COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    pip install --no-cache-dir uv \
    && uv pip install --system -r requirements.txt

COPY . .

# Drop root: run as an unprivileged user to shrink the blast radius of any RCE.
# media/ is the generated-assets root (settings.media_dir); creating it here
# with the right owner lets the prod named volume inherit those permissions.
RUN adduser --system --no-create-home --uid 1001 appuser \
    && mkdir -p /app/media && chown appuser /app/media
USER appuser

EXPOSE 8000
# --proxy-headers: in production uvicorn sits behind Caddy, so the real client
# IP arrives via X-Forwarded-For — without it every request appears to come
# from Caddy's IP and the per-IP rate limiter collapses into one shared bucket.
# Trusting "*" is safe here because the backend port is never published to the
# host in production (compose-internal network only; Caddy is the sole ingress).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
