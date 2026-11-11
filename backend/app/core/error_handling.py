"""Error handling: correlation IDs, RFC 9457 problem+json rendering, and observability.

Wired into the app by `install_error_handling(app)` in `app.main`. Three layers:

1. RequestIdMiddleware — stamps every request with an `error_id` (a.k.a.
   request id), echoed back in the `X-Request-ID` header and embedded in
   every error envelope as `instance`. Users report `code · ref`; support
   greps logs (or hits /api/ops/errors/{id}) for the exact request.
2. Handlers — AppError, request validation, bare HTTP errors, and a
   catch-all that renders ERR_SRV_001 without ever leaking exception text.
3. Observability — one structured JSON log line per error (greppable,
   alertable per-code) plus a short-lived Redis record with full request
   context for the ops lookup endpoint. A Sentry/OTel hook would go in
   `_record_error` — fingerprint by `code`, not stack trace, so repeats
   group into one issue.
"""

import json
import logging
import re
import traceback
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.error_codes import ERROR_CODES
from app.core.exceptions import AppError, ErrorParamValue, RateLimited
from app.core.policy import ERROR_CONTEXT_RETENTION_DAYS

logger = logging.getLogger("app.errors")

PROBLEM_MEDIA_TYPE = "application/problem+json"
ERROR_CONTEXT_TTL_SECONDS = ERROR_CONTEXT_RETENTION_DAYS * 24 * 3600
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
_LOG_LEVELS = {
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_redis: aioredis.Redis | None = None


def _redis_client() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a correlation id to every request (honoring a proxy-supplied one)."""

    async def dispatch(self, request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]


def _clean_params(code: str, params: dict[str, ErrorParamValue] | None) -> dict:
    """Keep only params the catalog declares for `code`, with scalar values.

    Anything else is a programming error at the raise site — log it rather
    than leak an unvetted value to the client."""
    if not params:
        return {}
    declared = set(ERROR_CODES[code]["params"])
    clean: dict[str, ErrorParamValue] = {}
    for name, value in params.items():
        scalar = isinstance(value, str | int | float) and not isinstance(value, bool)
        if name in declared and scalar:
            clean[name] = value
        else:
            logger.warning("dropping undeclared/invalid error param %s.%s", code, name)
    return clean


def problem_response(
    request: Request,
    code: str,
    *,
    detail: str | None = None,
    fields: dict[str, str] | None = None,
    params: dict[str, ErrorParamValue] | None = None,
    headers: dict[str, str] | None = None,
    status: int | None = None,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    """Render an RFC 9457 envelope for a catalog code.

    Extension members (all clients share these — web, mobile, API-key users):
      code            stable catalog code (ERR_<DOMAIN>_<NNN>)
      instance        correlation id (also the X-Request-ID header)
      retryable       true when repeating the same request may succeed
      retry_after_ms  suggested wait before retrying (only when retryable)
      params          values for the catalog copy's `{placeholders}`
      fields          per-field messages for form binding (validation only)
    """
    meta = ERROR_CODES[code]
    status = status or meta["status"]
    body: dict = {
        "type": f"{settings.frontend_url}/errors/{code}",
        "title": meta["title"],
        "status": status,
        "code": code,
        "instance": request_id_of(request),
        # `detail` keeps curl/non-catalog clients informed; the frontend
        # prefers its own catalog copy keyed by `code`.
        "detail": detail or meta["user_message"],
        "retryable": False,
    }
    if retry_after_seconds:
        body["retryable"] = True
        body["retry_after_ms"] = retry_after_seconds * 1000
        headers = {**(headers or {}), "Retry-After": str(retry_after_seconds)}
    elif meta["retry"]:
        body["retryable"] = True
        body["retry_after_ms"] = meta["retry"][0]
    if clean := _clean_params(code, params):
        body["params"] = clean
    if fields:
        body["fields"] = fields
    return JSONResponse(
        status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE, headers=headers
    )


# ---------------------------------------------------------------- validation copy

_LOC_PREFIXES = {"body", "query", "path", "header", "cookie"}


def field_key(loc: tuple | list) -> str:
    """pydantic loc -> dotted form-field key ("body.members.0.email" -> "members.0.email")."""
    parts = [str(part) for part in loc]
    if parts and parts[0] in _LOC_PREFIXES:
        parts = parts[1:]
    return ".".join(parts) or "__root__"


def _plural(n: object, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def friendly_field_message(err: dict) -> str:
    """Rewrite one pydantic error into a short, jargon-free sentence.

    Custom validators raise ValueError with user-facing copy; pydantic wraps
    that as "Value error, <copy>" — we strip the wrapper. Built-in error types
    get plain-language equivalents; anything unrecognized falls back to a
    generic sentence rather than pydantic's internals."""
    kind = err.get("type", "")
    ctx = err.get("ctx") or {}
    msg = str(err.get("msg", ""))

    if kind in ("value_error", "assertion_error"):
        if "valid email address" in msg:
            return "Enter a valid email address."
        for prefix in ("Value error, ", "Assertion failed, "):
            if msg.startswith(prefix):
                msg = msg[len(prefix) :]
        msg = msg.strip()
        return (msg[0].upper() + msg[1:]) if msg else "This value isn't valid."
    if kind == "missing":
        return "This field is required."
    if kind == "string_too_short":
        n = ctx.get("min_length", 1)
        return "This field is required." if n == 1 else f"Use at least {_plural(n, 'character')}."
    if kind == "string_too_long":
        return f"Use at most {_plural(ctx.get('max_length'), 'character')}."
    if kind == "too_short":
        return f"Add at least {_plural(ctx.get('min_length'), 'item')}."
    if kind == "too_long":
        return f"Use at most {_plural(ctx.get('max_length'), 'item')}."
    if kind in ("greater_than", "greater_than_equal", "less_than", "less_than_equal"):
        bound = next(iter(ctx.values()), None)
        phrase = {
            "greater_than": "more than",
            "greater_than_equal": "at least",
            "less_than": "less than",
            "less_than_equal": "at most",
        }[kind]
        if bound is None:
            return "Enter a value in range."
        return f"Enter a value {phrase} {bound}."
    if kind in ("int_parsing", "int_type", "int_from_float"):
        return "Enter a whole number."
    if kind in ("float_parsing", "float_type", "decimal_parsing", "decimal_type"):
        return "Enter a number."
    if kind in ("bool_parsing", "bool_type"):
        return "Choose yes or no."
    if kind in ("literal_error", "enum"):
        return "Choose one of the available options."
    if kind.startswith("url_"):
        return "Enter a valid link, starting with https://."
    if kind.startswith(("datetime_", "date_", "time_", "timezone_")):
        return "Enter a valid date and time."
    if kind.startswith("uuid_"):
        return "That reference isn't valid."
    if kind == "string_pattern_mismatch":
        return "This value isn't in the expected format."
    if kind == "extra_forbidden":
        return "This field isn't accepted here."
    if kind == "json_invalid":
        return "The request couldn't be read."
    return "This value isn't valid."


# Bare HTTPExceptions (framework 404/405s, webhook signature checks) map by
# status onto the closest generic catalog code, keeping status and code in
# agreement. Prefer raising an AppError subclass in application code.
_HTTP_STATUS_CODES = {
    400: "ERR_REQ_001",
    401: "ERR_AUTH_003",
    403: "ERR_PERM_001",
    404: "ERR_REQ_002",
    405: "ERR_REQ_002",
    409: "ERR_REQ_003",
    413: "ERR_REQ_005",
    422: "ERR_VAL_001",
    429: "ERR_REQ_004",
    503: "ERR_SRV_003",
}


def code_for_http_status(status: int) -> str:
    if status in _HTTP_STATUS_CODES:
        return _HTTP_STATUS_CODES[status]
    return "ERR_SRV_001" if status >= 500 else "ERR_REQ_001"


async def _record_error(request: Request, code: str, *, detail: str, tb: str | None = None) -> None:
    """Structured log line + Redis context record. Must never raise."""
    meta = ERROR_CODES.get(code, {"severity": "error", "status": 500})
    record = {
        "event": "error",
        "code": code,
        "error_id": request_id_of(request),
        "method": request.method,
        "path": request.url.path,
        "status": meta["status"],
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    logger.log(_LOG_LEVELS[meta["severity"]], json.dumps(record))

    context = {
        **record,
        "detail": detail,
        "query": str(request.url.query),
        "client": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }
    if tb:
        context["traceback"] = tb
    try:
        await _redis_client().set(
            f"errctx:{record['error_id']}", json.dumps(context), ex=ERROR_CONTEXT_TTL_SECONDS
        )
    except Exception:  # Redis being down must never break an error response
        logger.warning("errctx store unavailable for %s", record["error_id"])


def install_error_handling(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        await _record_error(request, exc.internal_code, detail=exc.message)
        retry_after = exc.retry_after if isinstance(exc, RateLimited) else None
        return problem_response(
            request,
            exc.internal_code,
            detail=exc.message,
            params=exc.params,
            retry_after_seconds=retry_after,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Flatten pydantic's loc/msg list into {field: message} for form
        # binding — first error per field wins, rewritten into plain copy.
        # The raw pydantic messages stay in the errctx record for support.
        fields: dict[str, str] = {}
        raw: dict[str, str] = {}
        for err in exc.errors():
            key = "__root__" if err.get("type") == "json_invalid" else field_key(err["loc"])
            if key not in fields:
                fields[key] = friendly_field_message(err)
                raw[key] = str(err.get("msg", ""))
        await _record_error(request, "ERR_VAL_001", detail=json.dumps(raw))
        return problem_response(request, "ERR_VAL_001", fields=fields)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Bare HTTPExceptions (unmatched routes, 405s, HTTPException raises)
        # still get a consistent envelope.
        code = code_for_http_status(exc.status_code)
        await _record_error(request, code, detail=str(exc.detail))
        return problem_response(
            request, code, detail=str(exc.detail), status=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # The traceback goes to logs + the errctx record — NEVER to the client.
        await _record_error(
            request,
            "ERR_SRV_001",
            detail=f"{type(exc).__name__}: {exc}",
            tb=traceback.format_exc(),
        )
        return problem_response(request, "ERR_SRV_001")

    app.add_middleware(RequestIdMiddleware)


async def lookup_error_context(error_id: str) -> dict | None:
    """Fetch the stored context for an error_id (ops lookup endpoint)."""
    raw = await _redis_client().get(f"errctx:{error_id}")
    return json.loads(raw) if raw else None
