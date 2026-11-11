"""FastAPI application factory: wires domain-slice routers together."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.core.error_handling import install_error_handling, problem_response
from app.core.idempotency import IdempotencyMiddleware
from app.core.observability import setup_sentry
from app.core.ratelimit import limiter
from app.core.security_headers import SecurityHeadersMiddleware
from app.domains.admin.interface.router import router as admin_router
from app.domains.analytics.interface.router import router as analytics_router
from app.domains.api_keys.interface.router import router as api_keys_router
from app.domains.audit.interface.router import router as audit_router
from app.domains.auth.interface.router import router as auth_router
from app.domains.billing.interface.admin_router import admin_router as billing_admin_router
from app.domains.billing.interface.router import router as billing_router
from app.domains.blog.interface.router import admin_router as blog_admin_router
from app.domains.blog.interface.router import public_router as blog_public_router
from app.domains.community.interface.router import (
    admin_router as community_admin_router,
)
from app.domains.community.interface.router import community_router
from app.domains.consents.interface.router import router as consents_router
from app.domains.credits.interface.router import router as credits_router
from app.domains.emails.interface.router import router as emails_router
from app.domains.entitlements.interface.router import admin_router as entitlements_admin_router
from app.domains.entitlements.interface.router import router as entitlements_router
from app.domains.feature_flags.interface.router import (
    admin_router as flags_admin_router,
)
from app.domains.feature_flags.interface.router import (
    public_router as flags_public_router,
)
from app.domains.files.interface.router import router as files_router
from app.domains.generations.interface.router import router as generations_router
from app.domains.llm.interface.router import router as llm_router
from app.domains.organizations.interface.router import router as organizations_router
from app.domains.privacy_requests.interface.router import (
    admin_router as privacy_admin_router,
)
from app.domains.privacy_requests.interface.router import (
    public_router as privacy_public_router,
)

setup_sentry()

app = FastAPI(
    title=settings.app_name,
    # Don't expose the API schema / Swagger UI in production.
    docs_url=None if settings.is_production else "/api/docs",
    openapi_url=None if settings.is_production else "/api/openapi.json",
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Replaces slowapi's default handler for a consistent problem+json envelope."""
    response = problem_response(
        request, "ERR_REQ_004", detail=f"Rate limit exceeded: {exc.detail}."
    )
    # Propagate the X-RateLimit-*/Retry-After headers like slowapi's handler does.
    if hasattr(request.state, "view_rate_limit"):
        response = request.app.state.limiter._inject_headers(
            response, request.state.view_rate_limit
        )
    return response


# RFC 9457 error envelope, correlation IDs, structured logs, errctx store —
# plus Idempotency-Key replay for mutating requests. AppError subclasses raised
# anywhere in a slice render through these handlers.
install_error_handling(app)
app.add_middleware(IdempotencyMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last = outermost: every response (errors, CORS preflights, idempotent
# replays) leaves with the baseline security headers.
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(admin_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(api_keys_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(organizations_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(billing_admin_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(entitlements_router, prefix="/api")
app.include_router(entitlements_admin_router, prefix="/api")
app.include_router(blog_public_router, prefix="/api")
app.include_router(blog_admin_router, prefix="/api")
app.include_router(community_router, prefix="/api")
app.include_router(community_admin_router, prefix="/api")
app.include_router(consents_router, prefix="/api")
app.include_router(credits_router, prefix="/api")
app.include_router(emails_router, prefix="/api")
app.include_router(flags_public_router, prefix="/api")
app.include_router(flags_admin_router, prefix="/api")
app.include_router(generations_router, prefix="/api")
app.include_router(llm_router, prefix="/api")
app.include_router(privacy_public_router, prefix="/api")
app.include_router(privacy_admin_router, prefix="/api")


@app.get("/api/health", tags=["health"])
async def health() -> dict[str, str]:
    """Readiness probe — gates zero-downtime deploys, so it must verify the DB."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok"}
