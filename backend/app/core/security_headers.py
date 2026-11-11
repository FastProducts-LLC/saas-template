"""Baseline security response headers, set by the app itself.

In the reference deployment Caddy adds these at the edge (and its values win —
Caddy's `header` directive replaces upstream ones). This middleware is the
floor for every other topology: a fork deployed behind a bare load balancer,
a PaaS router, or with the API port exposed directly still answers with safe
headers instead of none.

Pure ASGI (not BaseHTTPMiddleware) so streaming responses pass through
untouched. Headers a route already set are never overwritten.
"""

from app.core.config import settings

# The API serves JSON and files, never HTML that should run script — so the
# strictest CSP applies. Swagger UI (dev only) is exempt: it loads its bundle
# from a CDN.
_API_CSP = b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_CSP_EXEMPT_PATHS = ("/api/docs", "/api/redoc")


def _baseline_headers() -> list[tuple[bytes, bytes]]:
    headers = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
    ]
    if settings.is_production:
        # Only over real TLS deployments — never pin HSTS on a dev hostname.
        headers.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
    return headers


class SecurityHeadersMiddleware:
    def __init__(self, app) -> None:
        self.app = app
        self._headers = _baseline_headers()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with_csp = not scope.get("path", "").startswith(_CSP_EXEMPT_PATHS)

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                wanted = list(self._headers)
                if with_csp:
                    wanted.append((b"content-security-policy", _API_CSP))
                headers.extend((name, value) for name, value in wanted if name not in present)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
