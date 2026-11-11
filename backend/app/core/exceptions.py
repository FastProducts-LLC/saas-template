"""Application error hierarchy.

Feature slices raise these (or subclasses defined in their domain module);
the handlers in `app.core.error_handling` convert them to RFC 9457
problem+json responses.

Every class carries an `internal_code` that MUST exist in
`shared/errors.toml` (enforced by tests/test_error_contract.py). The legacy
`code` slug is kept for log readability.

`message` is developer-facing (logs, the errctx record, curl's `detail`) —
clients render the catalog copy instead. To put concrete values into that
copy, pass `params` whose names are declared in the code's catalog `params`
table, e.g. `InsufficientCredits(..., params={"required": 5, "available": 2})`.
Params are identifiers/numbers only: they cross the wire verbatim.
"""

ErrorParamValue = str | int | float


class AppError(Exception):
    status_code = 400
    code = "app_error"
    internal_code = "ERR_REQ_001"

    def __init__(
        self, message: str | None = None, *, params: dict[str, ErrorParamValue] | None = None
    ) -> None:
        self.message = message or self.code.replace("_", " ").capitalize()
        self.params: dict[str, ErrorParamValue] = dict(params or {})
        super().__init__(self.message)


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"
    internal_code = "ERR_AUTH_003"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    internal_code = "ERR_PERM_001"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    internal_code = "ERR_REQ_002"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    internal_code = "ERR_REQ_003"


class RateLimited(AppError):
    """Raised by rate-limiting dependencies; carries an optional Retry-After hint."""

    status_code = 429
    code = "rate_limited"
    internal_code = "ERR_REQ_004"

    def __init__(
        self,
        message: str | None = None,
        retry_after: int | None = None,
        *,
        params: dict[str, ErrorParamValue] | None = None,
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, params=params)


class StaleWriteError(ConflictError):
    """Optimistic-concurrency failure: the row changed since the client read it."""

    code = "stale_write"
    internal_code = "ERR_VAL_006"
